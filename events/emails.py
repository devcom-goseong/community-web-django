"""The emails an event produces.

Each function takes registration ids and fetches fresh rows, because they run
after the transaction commits and the objects the view held may be stale by
then. Every one of them is for something the member caused or is waiting for:
a confirmation, a place opening up, a reminder, a cancellation. Nothing here is
marketing, and nothing goes to an address that has not been confirmed.

The online link is included only in messages to people who have a place.
"""

from django.conf import settings
from django.utils import timezone

from content.emails import build_message, html_layout, send_each

from .ics import calendar_for
from .models import Registration


def _when(event):
    """For example "Thursday 24 September, 18:00–20:00 KST".

    The time zone is always written out: members outside Korea read these too.
    The day of the month is formatted by hand because strftime's %-d does not
    exist on Windows.
    """
    start = timezone.localtime(event.starts_at)
    end = timezone.localtime(event.ends_at)
    first = f"{start:%A} {start.day} {start:%B}, {start:%H:%M}"
    if start.date() == end.date():
        return f"{first}–{end:%H:%M} {start:%Z}"
    return f"{first} {start:%Z} to {end:%A} {end.day} {end:%B}, {end:%H:%M} {end:%Z}"


def _where(event, include_online):
    parts = []
    if event.location:
        parts.append(event.location)
    if event.online_url:
        parts.append(f"Online: {event.online_url}" if include_online else "Online")
    return " · ".join(parts) or "Details to follow"


def _event_url(event):
    return f"{settings.APP_URL}{event.get_absolute_url()}"


def _fetch(ids):
    return list(Registration.objects.filter(pk__in=ids)
                .select_related("event", "member__user"))


def _addressable(registration):
    member = registration.member
    return member.user.is_active and member.is_verified and bool(member.user.email)


def _ics_attachment(registration):
    event = registration.event
    content = calendar_for(event, include_online_link=True)
    return (f"{event.slug}.ics", content, "text/calendar")


def send_registration_email(registration_id):
    messages = []
    for registration in _fetch([registration_id]):
        if not _addressable(registration) or not registration.is_active:
            continue
        event = registration.event
        member = registration.member
        going = registration.status == Registration.Status.GOING
        if going:
            subject = f"You have a place: {event.title}"
            heading = "You have a place"
            lines = [
                f"Hello {member.display_name}, you are registered for {event.title}.",
                f"When: {_when(event)}\nWhere: {_where(event, include_online=True)}",
                "A calendar file is attached. If you cannot come after all, cancel from the "
                "event page so the place goes to someone on the waiting list.",
            ]
            attachments = [_ics_attachment(registration)]
        else:
            subject = f"You are on the waiting list: {event.title}"
            heading = "You are on the waiting list"
            lines = [
                f"Hello {member.display_name}, {event.title} is full, so you are on the "
                "waiting list.",
                f"When: {_when(event)}\nWhere: {_where(event, include_online=False)}",
                "If a place opens up before the event starts, it is given to the next person "
                "on the list automatically and we will email you straight away.",
            ]
            attachments = []
        text = "\n\n".join(lines) + f"\n\nEvent page: {_event_url(event)}\n\n--\n{settings.TEAM_NAME}\n"
        html = html_layout(heading, lines, button=("Open the event", _event_url(event)))
        messages.append(build_message(member.user.email, subject, text, html,
                                      attachments=attachments))
    return send_each(messages, "event registration email")


def send_promotion_emails(registration_ids):
    messages = []
    for registration in _fetch(registration_ids):
        if not _addressable(registration) or registration.status != Registration.Status.GOING:
            continue
        event = registration.event
        member = registration.member
        lines = [
            f"Hello {member.display_name}, a place opened up at {event.title} and it is yours.",
            f"When: {_when(event)}\nWhere: {_where(event, include_online=True)}",
            "You do not need to do anything to keep it. If you can no longer come, please "
            "cancel from the event page so it goes to the next person.",
        ]
        text = "\n\n".join(lines) + f"\n\nEvent page: {_event_url(event)}\n\n--\n{settings.TEAM_NAME}\n"
        html = html_layout("A place opened up for you", lines,
                           button=("Open the event", _event_url(event)))
        messages.append(build_message(
            member.user.email, f"A place opened up: {event.title}", text, html,
            attachments=[_ics_attachment(registration)]))
    return send_each(messages, "waiting list promotion email")


def send_event_cancelled_emails(registration_ids):
    messages = []
    for registration in _fetch(registration_ids):
        if not _addressable(registration):
            continue
        event = registration.event
        member = registration.member
        lines = [
            f"Hello {member.display_name}, {event.title} on {_when(event)} has been cancelled.",
            "Sorry for the change of plan. Your registration has been closed, and there is "
            "nothing you need to do.",
        ]
        text = "\n\n".join(lines) + f"\n\n--\n{settings.TEAM_NAME}\n"
        html = html_layout("An event you signed up for is cancelled", lines,
                           button=("See other events", f"{settings.APP_URL}/events/"))
        messages.append(build_message(
            member.user.email, f"Cancelled: {event.title}", text, html))
    return send_each(messages, "event cancellation email")


def send_event_changed_emails(registration_ids, changed_fields):
    labels = {"starts_at": "time", "ends_at": "time", "location": "place",
              "online_url": "online link"}
    what = " and ".join(sorted({labels[f] for f in changed_fields if f in labels}))
    messages = []
    for registration in _fetch(registration_ids):
        if not _addressable(registration) or not registration.is_active:
            continue
        event = registration.event
        member = registration.member
        has_place = registration.status == Registration.Status.GOING
        lines = [
            f"Hello {member.display_name}, the {what} for {event.title} has changed.",
            f"When: {_when(event)}\nWhere: {_where(event, include_online=has_place)}",
            "If you can no longer come, please cancel from the event page so the place goes "
            "to someone else.",
        ]
        text = "\n\n".join(lines) + f"\n\nEvent page: {_event_url(event)}\n\n--\n{settings.TEAM_NAME}\n"
        html = html_layout(f"The {what} has changed", lines,
                           button=("Open the event", _event_url(event)))
        attachments = [_ics_attachment(registration)] if has_place else []
        messages.append(build_message(
            member.user.email, f"Changed: {event.title}", text, html, attachments=attachments))
    return send_each(messages, "event change email")


def reminder_message(registration):
    event = registration.event
    member = registration.member
    lines = [
        f"Hello {member.display_name}, a reminder that {event.title} is coming up.",
        f"When: {_when(event)}\nWhere: {_where(event, include_online=True)}",
        "If you can no longer come, please cancel from the event page so your place goes to "
        "someone on the waiting list.",
    ]
    text = "\n\n".join(lines) + f"\n\nEvent page: {_event_url(event)}\n\n--\n{settings.TEAM_NAME}\n"
    html = html_layout("Coming up soon", lines, button=("Open the event", _event_url(event)))
    return build_message(member.user.email, f"Reminder: {event.title}", text, html)
