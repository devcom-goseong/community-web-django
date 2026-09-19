"""The events list, an event's page, signing up, cancelling, and the calendar file."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from accounts.access import access_state, can_see_members_area, member_of
from config.ratelimit import rate_limited
from content.seo import event_ld
from content.views import base_context

from . import services
from .ics import calendar_for
from .models import Event, Registration

PAST_EVENTS_SHOWN = 12


def _restricted(request, event_slug=None):
    """The same answer whether an event does not exist or is not for this person.

    Otherwise the difference between "not found" and "sign in to see this"
    would tell anyone which addresses belong to members-only events.
    """
    context = base_context(request, "Event not available",
                           "This event does not exist, or it is only visible to members.",
                           nav="events")
    context.update({"kind": "event", "next": request.get_full_path(),
                    "state": access_state(request.user), "noindex": True})
    response = render(request, "members/restricted.html", context, status=404)
    response["X-Robots-Tag"] = "noindex"
    return response


def event_list(request):
    now = timezone.now()
    visible = Event.objects.visible_to(request.user).select_related("activity").with_counts()
    upcoming = list(visible.upcoming(now).order_by("starts_at", "pk"))
    past = list(visible.past(now).filter(status=Event.Status.PUBLISHED)
                .order_by("-starts_at", "-pk")[:PAST_EVENTS_SHOWN])

    mine = {}
    member = member_of(request.user)
    if member:
        mine = dict(Registration.objects.filter(
            member=member, event__in=[e.pk for e in upcoming],
            status__in=[Registration.Status.GOING, Registration.Status.WAITLIST],
        ).values_list("event_id", "status"))
    for event in upcoming:
        event.my_status = mine.get(event.pk)

    context = base_context(
        request, "Events",
        "What the community has coming up: weekly meetings, meetups, hackathons and demo days.",
        nav="events")
    context.update({"upcoming": upcoming, "past": past})
    return render(request, "events/list.html", context)


def event_detail(request, slug):
    event = (Event.objects.filter(slug=slug).select_related("activity").with_counts().first())
    if event is None or not event.visible_to(request.user):
        return _restricted(request, slug)

    now = timezone.now()
    member = member_of(request.user)
    registration = (Registration.objects.filter(event=event, member=member).first()
                    if member else None)
    if registration and not registration.is_active:
        registration = None

    block = services.registration_block(event, request.user, now)

    # Who is going. Names only for people whose profile is visible to members,
    # and only to viewers who are members themselves; everyone else is a number.
    going = list(event.registrations.filter(status=Registration.Status.GOING)
                 .select_related("member__user").order_by("joined_at", "pk"))
    named, unnamed = [], 0
    viewer_sees_members = can_see_members_area(request.user)
    for item in going:
        if viewer_sees_members and item.member.is_listed:
            named.append(item.member)
        else:
            unnamed += 1

    context = base_context(request, event.title, event.summary, nav="events")
    context.update({
        "event": event,
        "registration": registration,
        "has_place": bool(registration and registration.status == Registration.Status.GOING),
        "block": block,
        "block_message": services.MESSAGES.get(block, "") if block else "",
        "named_attendees": named,
        "unnamed_attendees": unnamed,
        "spots_left": event.spots_left(),
        "has_started": event.has_started(now),
        "has_ended": event.has_ended(now),
        "can_cancel": bool(registration and not event.has_started(now)),
        # Rich-result data for a public event; empty for members-only or drafts.
        "event_ld": event_ld(request, event),
    })
    response = render(request, "events/detail.html", context)
    if event.visibility == Event.Visibility.MEMBERS or registration:
        response["Cache-Control"] = "private, no-cache"
    return response


def _back(event):
    return redirect(event.get_absolute_url())


@require_POST
def event_register(request, slug):
    event = Event.objects.filter(slug=slug).first()
    if event is None or not event.visible_to(request.user):
        return _restricted(request, slug)
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={event.get_absolute_url()}")

    # Generous, because signing up for several events in a row is normal; the
    # limit is only there to stop the button being used to generate email.
    if rate_limited(request, scope="events", limit=30):
        messages.error(request, "Too many changes in a short time. Please wait a few minutes.")
        return _back(event)

    try:
        _registration, outcome = services.register(event, request.user)
    except services.RegistrationError as error:
        messages.error(request, error.message)
        return _back(event)

    if outcome == Registration.Status.GOING:
        messages.success(request, "You have a place. A confirmation is on its way to your inbox.")
    elif outcome == Registration.Status.WAITLIST:
        messages.info(request, "The event is full, so you are on the waiting list. If a place "
                               "opens up it is yours automatically, and we will email you.")
    else:
        messages.info(request, "You are already registered for this event.")
    return _back(event)


@require_POST
def event_cancel(request, slug):
    event = Event.objects.filter(slug=slug).first()
    if event is None or not event.visible_to(request.user):
        return _restricted(request, slug)
    if not request.user.is_authenticated:
        return redirect(f"{reverse('accounts:login')}?next={event.get_absolute_url()}")

    if rate_limited(request, scope="events", limit=30):
        messages.error(request, "Too many changes in a short time. Please wait a few minutes.")
        return _back(event)

    try:
        services.cancel(event, request.user)
    except services.RegistrationError as error:
        messages.error(request, error.message)
        return _back(event)

    messages.success(request, "Your registration is cancelled. Thank you for freeing the place.")
    return _back(event)


@require_GET
@never_cache
def event_calendar(request, slug):
    event = Event.objects.filter(slug=slug).first()
    if event is None or not event.visible_to(request.user):
        return _restricted(request, slug)

    member = member_of(request.user)
    has_place = bool(member and Registration.objects.filter(
        event=event, member=member, status=Registration.Status.GOING).exists())

    response = HttpResponse(
        calendar_for(event, include_online_link=has_place),
        content_type="text/calendar; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{event.slug}.ics"'
    return response
