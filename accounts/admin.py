"""Members in the admin.

The `Member` row is shown inline on the user it belongs to, because they are
one thing to the person reading the page, and separately in its own list,
because "show me everyone awaiting review" is the question the leadership team
actually asks.

A member's status is never written straight to the database from here. Changing
it has consequences — an approval email, places at events given up, a profile
taken down — and those live in accounts.services.change_status. The actions and
the edit page both go through it; the inline on the user page shows the status
but does not let it be changed there.
"""

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth.models import User
from django.utils.html import format_html

from .emails import send_welcome_email
from .models import Member, MemberProject
from .services import change_status

RECORD_FIELDS = ("email_verified_at", "approved_at", "accepted_documents", "accepted_at",
                 "created_at", "updated_at")


class MemberInline(admin.StackedInline):
    model = Member
    can_delete = False
    extra = 0
    readonly_fields = ("status",) + RECORD_FIELDS
    fieldsets = (
        (None, {
            "fields": ("display_name", "handle", "status", "notes"),
            "description": "To approve, pause or remove this person, use the Members list, so "
                           "the emails are sent and event places are handled.",
        }),
        ("Profile", {"fields": ("profile_visibility", "bio", "interests", "github_url",
                                "linkedin_url")}),
        ("Student details", {"fields": ("student", "student_id")}),
        ("Record", {
            "fields": RECORD_FIELDS,
            "description": "What they accepted and when. Not editable: it is the record.",
        }),
    )


class UserAdminForm(UserChangeForm):
    """Refuse an email address a different account already uses.

    The database enforces this too, with a case-insensitive unique index, but a
    form error names the problem here instead of letting the save fail with a
    500. The rule matches the sign-up form: addresses are compared case-insens-
    itively, and a blank one is allowed (an account may have none).
    """

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if email:
            clash = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
            if clash.exists():
                raise forms.ValidationError(
                    "Another account already uses this email address.")
        return email


class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    inlines = (MemberInline,)
    list_display = ("email", "first_name", "member_status", "is_staff", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active", "member__status")
    ordering = ("-date_joined",)
    search_fields = ("email", "first_name", "last_name", "username")

    @admin.display(description="member", ordering="member__status")
    def member_status(self, obj):
        member = getattr(obj, "member", None)
        if member is None:
            return "—"
        mark = "confirmed" if member.is_verified else "unconfirmed"
        return format_html("{} · {}", member.get_status_display(), mark)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


class ProjectInline(admin.TabularInline):
    model = MemberProject
    extra = 0
    fields = ("title", "url", "description", "order")


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "handle", "email", "status", "verified",
                    "profile_visibility", "approved_at", "created_at")
    list_filter = ("status", "profile_visibility", "student", "created_at")
    search_fields = ("display_name", "handle", "user__email", "student_id")
    readonly_fields = ("user",) + RECORD_FIELDS
    actions = ("approve", "pause", "remove", "hide_profile", "resend_confirmation")
    date_hierarchy = "created_at"
    inlines = (ProjectInline,)

    fieldsets = (
        (None, {"fields": ("user", "display_name", "handle", "status", "notes")}),
        ("Profile", {
            "fields": ("profile_visibility", "bio", "interests", "github_url", "linkedin_url"),
            "description": "If a profile breaks the community rules, set it to 'Only me' and "
                           "remove whatever broke them. The member will see the change on "
                           "their own account.",
        }),
        ("Student details", {"fields": ("student", "student_id")}),
        ("Record", {
            "fields": RECORD_FIELDS,
            "description": "What they accepted and when. Not editable: it is the record.",
        }),
    )

    @admin.display(boolean=True, description="email confirmed")
    def verified(self, obj):
        return obj.is_verified

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    def has_delete_permission(self, request, obj=None):
        # Deleting only the member row would leave a login with nothing behind
        # it. To delete someone entirely, delete their user; to take them out
        # of the community, use Remove.
        return False

    def save_model(self, request, obj, form, change):
        new_status = obj.status
        if change and "status" in form.changed_data:
            # Save everything else with the old status, then change the status
            # through the service so its consequences happen.
            obj.status = form.initial.get("status", obj.status)
            super().save_model(request, obj, form, change)
            change_status(obj, new_status)
            self._explain(request, obj, new_status)
        else:
            super().save_model(request, obj, form, change)

    def _explain(self, request, member, status):
        if status == Member.Status.ACTIVE and not member.is_verified:
            self.message_user(
                request,
                f"{member.display_name} is approved, but has not confirmed their email address. "
                f"They will have access as soon as they do.", messages.WARNING)

    def _apply(self, request, queryset, status, label):
        changed = unconfirmed = 0
        for member in queryset.select_related("user"):
            if change_status(member, status):
                changed += 1
                if status == Member.Status.ACTIVE and not member.is_verified:
                    unconfirmed += 1
        self.message_user(request, f"{changed} {label}.", messages.SUCCESS)
        if unconfirmed:
            self.message_user(
                request,
                f"{unconfirmed} of those have not confirmed their email address yet, so they "
                f"will get access, and the welcome email, once they do.", messages.WARNING)

    @admin.action(description="Approve as members (sends the welcome-in email)")
    def approve(self, request, queryset):
        self._apply(request, queryset, Member.Status.ACTIVE, "approved")

    @admin.action(description="Pause membership (gives up their event places)")
    def pause(self, request, queryset):
        self._apply(request, queryset, Member.Status.PAUSED, "paused")

    @admin.action(description="Remove from the community (hides the profile too)")
    def remove(self, request, queryset):
        self._apply(request, queryset, Member.Status.REMOVED, "removed")

    @admin.action(description="Hide profile (set to 'Only me')")
    def hide_profile(self, request, queryset):
        updated = queryset.exclude(profile_visibility=Member.Visibility.HIDDEN).update(
            profile_visibility=Member.Visibility.HIDDEN)
        self.message_user(request, f"{updated} profiles hidden.", messages.SUCCESS)

    @admin.action(description="Send the confirmation email again")
    def resend_confirmation(self, request, queryset):
        sent = failed = 0
        for member in queryset.select_related("user"):
            if member.is_verified:
                continue
            if send_welcome_email(member, request):
                sent += 1
            else:
                failed += 1
        self.message_user(request, f"{sent} sent.", messages.SUCCESS)
        if failed:
            self.message_user(request, f"{failed} could not be sent.", messages.ERROR)
