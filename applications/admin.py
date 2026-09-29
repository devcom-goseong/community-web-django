from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "intent", "student", "status", "interests_summary",
                    "emails_ok", "created_at")
    list_filter = ("status", "intent", "student", "accepted_documents", "created_at")
    search_fields = ("name", "email", "student_id", "message")
    date_hierarchy = "created_at"
    list_per_page = 50
    ordering = ("-created_at",)
    actions = ("mark_reviewing", "mark_accepted", "mark_declined", "mark_spam")

    readonly_fields = ("intent", "name", "email", "student", "student_id", "interests",
                       "message", "consented_to_contact", "accepted_documents", "accepted_at",
                       "confirmation_sent", "notification_sent", "created_at")

    fieldsets = (
        ("Who wrote in", {"fields": ("name", "email", "student", "student_id", "created_at")}),
        ("What they said", {"fields": ("intent", "interests", "message")}),
        ("What they agreed to", {
            "fields": ("accepted_documents", "consented_to_contact", "accepted_at"),
            "description": "Recorded at submission. Read-only, because it is the evidence "
                           "that the rules, terms and privacy notice were accepted.",
        }),
        ("Review", {"fields": ("status", "review_notes", "reviewed_by", "reviewed_at")}),
        ("Delivery", {"fields": ("notification_sent", "confirmation_sent"), "classes": ("collapse",)}),
    )

    @admin.display(description="interests")
    def interests_summary(self, obj):
        if not obj.interests:
            return "—"
        shown = ", ".join(obj.interests[:2])
        return f"{shown} +{len(obj.interests) - 2}" if len(obj.interests) > 2 else shown

    @admin.display(description="emails", boolean=False)
    def emails_ok(self, obj):
        if obj.notification_sent and obj.confirmation_sent:
            return "both sent"
        if obj.notification_sent:
            return format_html('<span title="the applicant was not confirmed">team only</span>')
        return format_html('<strong title="nobody was emailed">none sent</strong>')

    def has_add_permission(self, request):
        # Applications arrive through the form, never by hand.
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if "status" in form.changed_data and obj.status == Application.Status.ACCEPTED:
            # The same as the list action, for an application accepted from
            # its own page.
            from accounts.services import accept_applications

            created, approved = accept_applications([obj], request)
            self._report_accept(request, created, approved)

    def _set_status(self, request, queryset, status, label):
        updated = queryset.update(status=status, reviewed_by=request.user,
                                  reviewed_at=timezone.now())
        self.message_user(request, f"{updated} marked {label}.", messages.SUCCESS)

    @admin.action(description="Mark as being reviewed")
    def mark_reviewing(self, request, queryset):
        self._set_status(request, queryset, Application.Status.REVIEWING, "as being reviewed")

    @admin.action(description="Mark as accepted (creates or approves the member account)")
    def mark_accepted(self, request, queryset):
        applications = list(queryset)
        self._set_status(request, queryset, Application.Status.ACCEPTED, "accepted")

        # Accepting is what makes someone a member: for each join application it
        # creates the account (and emails a set-a-password link) or, if one was
        # already made by hand, approves it. Only confirmed accounts are approved;
        # a newly created account is confirmed for them, since only they receive
        # the link.
        from accounts.services import accept_applications

        created, approved = accept_applications(applications, request)
        self._report_accept(request, created, approved)

    def _report_accept(self, request, created, approved):
        if created:
            self.message_user(
                request,
                f"{created} member account(s) created — a set-a-password email is on the way.",
                messages.SUCCESS)
        if approved:
            self.message_user(
                request, f"{approved} existing member account(s) approved as well.",
                messages.SUCCESS)

    @admin.action(description="Mark as declined")
    def mark_declined(self, request, queryset):
        self._set_status(request, queryset, Application.Status.DECLINED, "declined")

    @admin.action(description="Mark as spam")
    def mark_spam(self, request, queryset):
        self._set_status(request, queryset, Application.Status.SPAM, "spam")
