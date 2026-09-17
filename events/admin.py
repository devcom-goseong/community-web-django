"""Events in the admin.

A few things here exist to stop the admin quietly breaking the promises the
site makes:

  * A registration's status cannot be typed into a box. Moving someone from
    "has a place" to "cancelled" by hand would free a place without offering it
    to the waiting list. Status changes go through actions that run the same
    code the site does, and every save of an event settles the waiting list
    afterwards, which also covers raising the capacity.
  * An event with registrations cannot be deleted, because that would erase
    attendance from members' profiles. Cancel it instead.
  * The address of an event is fixed once it exists, so shared links keep
    working.
  * The attendee export escapes cells that a spreadsheet would run as a
    formula, and starts with a byte-order mark so Excel reads Korean names
    correctly instead of as garbage.
"""

import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.utils import timezone

from . import services
from .models import Event, Registration


class RegistrationInline(admin.TabularInline):
    model = Registration
    extra = 0
    fields = ("member", "status", "role", "attended", "joined_at", "cancelled_at")
    readonly_fields = ("member", "status", "joined_at", "cancelled_at")
    ordering = ("status", "joined_at")
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        # People register through the site, so the waiting list stays fair.
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "starts_local", "status", "visibility", "audience", "places",
                    "waiting", "activity")
    list_filter = ("status", "visibility", "audience", "activity")
    search_fields = ("title", "summary", "location")
    date_hierarchy = "starts_at"
    inlines = (RegistrationInline,)
    actions = ("publish", "cancel_and_notify", "mark_going_as_attended", "export_attendees")
    readonly_fields = ("cancelled_at", "created_by", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("title", "slug", "activity", "summary", "description")}),
        ("When and where", {
            "fields": ("starts_at", "ends_at", "location", "online_url"),
            "description": "Times are in Korean time (KST). The online link is only ever "
                           "shown to people who have a place.",
        }),
        ("Registration", {"fields": ("capacity", "registration_closes_at", "audience")}),
        ("Publishing", {
            "fields": ("visibility", "status"),
            "description": "To call an event off, use the 'Cancel and notify' action from the "
                           "list rather than changing the status here — the action emails "
                           "everyone who signed up.",
        }),
        ("Record", {"fields": ("cancelled_at", "created_by", "created_at", "updated_at"),
                    "classes": ("collapse",)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("activity").with_counts()

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj is not None:
            fields.append("slug")
        return fields

    @admin.display(description="starts", ordering="starts_at")
    def starts_local(self, obj):
        return timezone.localtime(obj.starts_at).strftime("%Y-%m-%d %H:%M %Z")

    @admin.display(description="places")
    def places(self, obj):
        return f"{obj.going_total} / {obj.capacity}" if obj.capacity else f"{obj.going_total}"

    @admin.display(description="waiting")
    def waiting(self, obj):
        return obj.waitlist_total or "—"

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        if change and "status" in form.changed_data and obj.status == Event.Status.CANCELLED:
            # Changing the status field by hand would skip the emails. Put it
            # back and cancel properly once everything else is saved.
            obj.status = form.initial.get("status", Event.Status.PUBLISHED)
            request._cancel_after_save = True
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        event = form.instance
        if change and not getattr(request, "_cancel_after_save", False):
            told = services.notify_changes(event, form.changed_data)
            if told:
                self.message_user(
                    request, f"The time or place changed, so {told} people who signed up are "
                             f"being emailed the new details.", messages.INFO)
        if getattr(request, "_cancel_after_save", False):
            notified = services.cancel_event(event)
            self.message_user(
                request, f"Cancelled. {notified} people who signed up are being emailed.",
                messages.WARNING)
        else:
            promoted = services.settle_waiting_list(event)
            if promoted:
                self.message_user(
                    request,
                    f"{len(promoted)} people moved from the waiting list to a place, and are "
                    f"being emailed.", messages.SUCCESS)

    @admin.action(description="Publish")
    def publish(self, request, queryset):
        updated = queryset.filter(status=Event.Status.DRAFT).update(status=Event.Status.PUBLISHED)
        self.message_user(request, f"{updated} published.", messages.SUCCESS)

    @admin.action(description="Cancel and notify everyone who signed up")
    def cancel_and_notify(self, request, queryset):
        total = events = 0
        for event in queryset:
            if event.status != Event.Status.CANCELLED:
                total += services.cancel_event(event)
                events += 1
        self.message_user(
            request, f"{events} cancelled. {total} people are being emailed.", messages.WARNING)

    @admin.action(description="Mark everyone with a place as attended (after the event)")
    def mark_going_as_attended(self, request, queryset):
        now = timezone.now()
        finished = queryset.filter(ends_at__lte=now, status=Event.Status.PUBLISHED)
        skipped = queryset.count() - finished.count()
        updated = Registration.objects.filter(
            event__in=finished, status=Registration.Status.GOING, attended__isnull=True,
        ).update(attended=True)
        self.message_user(
            request, f"{updated} marked as attended. Anyone who did not come can be changed "
                     f"on the event's page.", messages.SUCCESS)
        if skipped:
            self.message_user(
                request, f"{skipped} event(s) skipped: not finished yet, or cancelled.",
                messages.WARNING)

    @admin.action(description="Export attendees as a spreadsheet (CSV)")
    def export_attendees(self, request, queryset):
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
        response["Content-Disposition"] = f'attachment; filename="attendees-{stamp}.csv"'
        response.write("﻿")

        writer = csv.writer(response)
        writer.writerow(["event", "starts", "name", "email", "status", "role", "attended",
                         "signed up"])
        registrations = (Registration.objects.filter(event__in=queryset)
                         .exclude(status=Registration.Status.CANCELLED)
                         .select_related("event", "member__user")
                         .order_by("event__starts_at", "status", "joined_at"))
        for r in registrations:
            writer.writerow([_cell(v) for v in (
                r.event.title,
                timezone.localtime(r.event.starts_at).strftime("%Y-%m-%d %H:%M"),
                r.member.display_name,
                r.member.user.email,
                r.get_status_display(),
                r.get_role_display(),
                {True: "yes", False: "no", None: ""}[r.attended],
                timezone.localtime(r.joined_at).strftime("%Y-%m-%d %H:%M"),
            )])
        return response


def _cell(value):
    """Stop a spreadsheet treating a member's text as a formula.

    A display name of "=HYPERLINK(...)" is text on the site, but a spreadsheet
    opening the export would run it. Prefixing a quote keeps it as text.
    """
    text = str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + text
    return text


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ("member", "event", "status", "role", "attended", "joined_at")
    list_filter = ("status", "role", "attended", "event")
    list_editable = ("role", "attended")
    search_fields = ("member__display_name", "member__user__email", "event__title")
    readonly_fields = ("event", "member", "status", "joined_at", "cancelled_at",
                       "reminder_sent_at", "created_at", "updated_at")
    actions = ("cancel_registrations", "mark_attended", "mark_absent")
    list_select_related = ("member", "event")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        # Deleting a registration would free a place without offering it to
        # the waiting list. Cancelling does both.
        return False

    @admin.action(description="Cancel (frees the place for the waiting list)")
    def cancel_registrations(self, request, queryset):
        cancelled = 0
        for registration in queryset.select_related("event", "member__user"):
            if not registration.is_active:
                continue
            try:
                services.cancel(registration.event, registration.member.user)
                cancelled += 1
            except services.RegistrationError as error:
                self.message_user(
                    request, f"{registration.member.display_name}: {error.message}",
                    messages.WARNING)
        self.message_user(request, f"{cancelled} cancelled.", messages.SUCCESS)

    @admin.action(description="Mark as attended")
    def mark_attended(self, request, queryset):
        updated = queryset.update(attended=True)
        self.message_user(request, f"{updated} marked as attended.", messages.SUCCESS)

    @admin.action(description="Mark as did not attend")
    def mark_absent(self, request, queryset):
        updated = queryset.update(attended=False)
        self.message_user(request, f"{updated} marked as not attended.", messages.SUCCESS)
