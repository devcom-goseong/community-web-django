"""Members in the admin.

The `Member` row is shown inline on the user it belongs to, because they are
one thing to the person reading the page, and separately in its own list,
because "show me everyone awaiting review" is the question the leadership team
actually asks.
"""

from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from .emails import send_welcome_email
from .models import Member


class MemberInline(admin.StackedInline):
    model = Member
    can_delete = False
    extra = 0
    readonly_fields = ("email_verified_at", "accepted_documents", "accepted_at",
                       "created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("display_name", "status", "notes")}),
        ("About them", {"fields": ("student", "student_id", "interests", "bio",
                                   "github_url", "linkedin_url")}),
        ("Record", {
            "fields": ("email_verified_at", "accepted_documents", "accepted_at",
                       "created_at", "updated_at"),
            "description": "What they accepted and when. Not editable: it is the record.",
        }),
    )


class UserAdmin(BaseUserAdmin):
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


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ("display_name", "email", "status", "verified", "student", "created_at")
    list_filter = ("status", "student", "created_at")
    search_fields = ("display_name", "user__email", "student_id")
    readonly_fields = ("user", "email_verified_at", "accepted_documents", "accepted_at",
                       "created_at", "updated_at")
    actions = ("approve", "pause", "resend_confirmation")
    date_hierarchy = "created_at"

    fieldsets = (
        (None, {"fields": ("user", "display_name", "status", "notes")}),
        ("About them", {"fields": ("student", "student_id", "interests", "bio",
                                   "github_url", "linkedin_url")}),
        ("Record", {
            "fields": ("email_verified_at", "accepted_documents", "accepted_at",
                       "created_at", "updated_at"),
            "description": "What they accepted and when. Not editable: it is the record.",
        }),
    )

    @admin.display(boolean=True, description="email confirmed")
    def verified(self, obj):
        return obj.is_verified

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user")

    @admin.action(description="Approve as a member")
    def approve(self, request, queryset):
        unconfirmed = queryset.filter(email_verified_at__isnull=True).count()
        changed = queryset.update(status=Member.Status.ACTIVE)
        self.message_user(request, f"{changed} approved.", messages.SUCCESS)
        if unconfirmed:
            self.message_user(
                request,
                f"{unconfirmed} of those has not confirmed their email address yet.",
                messages.WARNING)

    @admin.action(description="Pause membership")
    def pause(self, request, queryset):
        changed = queryset.update(status=Member.Status.PAUSED)
        self.message_user(request, f"{changed} paused.", messages.SUCCESS)

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
