"""Signing up, cancelling, and moving people off the waiting list.

Everything that changes who has a place goes through here, for two reasons.

Places are a shared resource. Two people pressing "Register" for the last place
at the same moment must not both get it, so every change locks the event's row
first (SELECT ... FOR UPDATE) and does its counting inside that lock. On
PostgreSQL that serialises them; SQLite serialises all writes anyway.

The waiting list is a promise. Whoever joined it first moves up first, nobody
jumps it — not a new sign-up that happens to arrive just as a place frees, not
someone who cancelled and signed up again. So the list is always settled before
a new registration is counted.

Emails are sent after the transaction commits, never inside it. If the
database work rolls back, nobody is told they have a place they do not have.
"""

import logging

from django.db import transaction
from django.utils import timezone

from accounts.access import is_staff, member_of

from .models import Event, Registration

log = logging.getLogger(__name__)


class RegistrationError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code

    @property
    def message(self):
        return MESSAGES.get(self.code, "That could not be done.")


# Plain explanations for every refusal, written for the person who hit it.
MESSAGES = {
    "sign-in": "Sign in to register for events.",
    "no-member": "This account is not a member account, so it cannot register. "
                 "Leadership team accounts should register with a personal account.",
    "unconfirmed": "Confirm your email address first — the link is in your welcome email.",
    "members-only": "This event is for approved members. You can register once your "
                    "membership has been approved.",
    "inactive": "Your membership is paused, so you cannot register for events right now.",
    "draft": "This event has not been published yet.",
    "cancelled": "This event has been cancelled.",
    "started": "This event has already started.",
    "closed": "Registration for this event has closed.",
    "not-registered": "You are not registered for this event.",
    "too-late-to-cancel": "This event has already started, so the registration cannot be "
                          "cancelled.",
}


def member_is_eligible(event, member):
    """Whether this member may hold a place at this event right now.

    Checked on sign-up, and again for each person before they are moved off
    the waiting list, because someone can be paused while they wait.
    """
    if member is None or not member.user.is_active or not member.is_verified:
        return False
    if member.status in {member.Status.PAUSED, member.Status.REMOVED}:
        return False
    if event.audience == Event.Audience.MEMBERS:
        return member.status == member.Status.ACTIVE
    return True


def registration_block(event, user, now=None):
    """Why this user cannot register, as a code, or None if they can."""
    now = now or timezone.now()
    if not getattr(user, "is_authenticated", False):
        return "sign-in"
    if event.status == Event.Status.DRAFT:
        return "draft"
    if event.status == Event.Status.CANCELLED:
        return "cancelled"
    if event.has_started(now):
        return "started"
    if now >= event.registration_deadline:
        return "closed"

    member = member_of(user)
    if member is None or not user.is_active:
        return "no-member"
    if not member.is_verified:
        return "unconfirmed"
    if member.status in {member.Status.PAUSED, member.Status.REMOVED}:
        return "inactive"
    if not event.visible_to(user) and not is_staff(user):
        return "members-only"
    if event.audience == Event.Audience.MEMBERS and member.status != member.Status.ACTIVE:
        return "members-only"
    return None


def _locked(event_id):
    return Event.objects.select_for_update().get(pk=event_id)


def _settle_waiting_list(event, now):
    """Fill free places from the waiting list, in order. Needs the event lock.

    Returns the registrations that were given a place. Anyone who is no longer
    eligible — paused, say, while they waited — is taken off the list rather
    than handed a place they cannot use.
    """
    if event.status != Event.Status.PUBLISHED or event.has_started(now):
        return []

    going = event.registrations.filter(status=Registration.Status.GOING).count()
    free = None if event.capacity is None else event.capacity - going
    if free is not None and free <= 0:
        return []

    promoted = []
    waiting = (event.registrations.filter(status=Registration.Status.WAITLIST)
               .select_related("member__user").order_by("joined_at", "pk"))
    for registration in waiting:
        if free is not None and len(promoted) >= free:
            break
        if not member_is_eligible(event, registration.member):
            registration.status = Registration.Status.CANCELLED
            registration.cancelled_at = now
            registration.save(update_fields=["status", "cancelled_at", "updated_at"])
            continue
        registration.status = Registration.Status.GOING
        registration.save(update_fields=["status", "updated_at"])
        promoted.append(registration)

    if promoted:
        ids = [r.pk for r in promoted]
        transaction.on_commit(lambda: _send_promotions(ids))
    return promoted


def _send_promotions(ids):
    from .emails import send_promotion_emails

    send_promotion_emails(ids)


def register(event, user):
    """Give this user a place, or a place on the waiting list.

    Returns (registration, outcome) where outcome is "going", "waitlist" or
    "already". Raises RegistrationError if they cannot register.
    """
    with transaction.atomic():
        event = _locked(event.pk)
        now = timezone.now()
        code = registration_block(event, user, now)
        if code:
            raise RegistrationError(code)

        member = member_of(user)
        existing = Registration.objects.filter(event=event, member=member).first()
        if existing and existing.is_active:
            return existing, "already"

        # Settle the list first, so a new arrival can never take a place that
        # belongs to someone already waiting.
        _settle_waiting_list(event, now)
        going = event.registrations.filter(status=Registration.Status.GOING).count()
        has_room = event.capacity is None or going < event.capacity
        status = Registration.Status.GOING if has_room else Registration.Status.WAITLIST

        if existing:
            existing.status = status
            existing.joined_at = now
            existing.cancelled_at = None
            existing.reminder_sent_at = None
            existing.save(update_fields=["status", "joined_at", "cancelled_at",
                                         "reminder_sent_at", "updated_at"])
            registration = existing
        else:
            registration = Registration.objects.create(
                event=event, member=member, status=status, joined_at=now)

        registration_id = registration.pk
        transaction.on_commit(lambda: _send_confirmation(registration_id))
        return registration, status


def _send_confirmation(registration_id):
    from .emails import send_registration_email

    send_registration_email(registration_id)


def cancel(event, user):
    """Give up a place, or leave the waiting list. Returns the promoted registrations."""
    with transaction.atomic():
        event = _locked(event.pk)
        now = timezone.now()
        member = member_of(user)
        registration = (Registration.objects.filter(event=event, member=member).first()
                        if member else None)
        if registration is None or not registration.is_active:
            raise RegistrationError("not-registered")
        if event.has_started(now):
            raise RegistrationError("too-late-to-cancel")

        was_going = registration.status == Registration.Status.GOING
        registration.status = Registration.Status.CANCELLED
        registration.cancelled_at = now
        registration.save(update_fields=["status", "cancelled_at", "updated_at"])
        return _settle_waiting_list(event, now) if was_going else []


def settle_waiting_list(event):
    """Promote from the waiting list after an admin change, such as a bigger capacity."""
    with transaction.atomic():
        event = _locked(event.pk)
        return _settle_waiting_list(event, timezone.now())


def cancel_event(event):
    """Mark an event cancelled and tell everyone who had a place or was waiting.

    The registrations are left as they were, as a record of who had signed up.
    A cancelled event never appears on anyone's profile.
    """
    with transaction.atomic():
        event = _locked(event.pk)
        if event.status == Event.Status.CANCELLED:
            return 0
        event.status = Event.Status.CANCELLED
        event.cancelled_at = timezone.now()
        event.save(update_fields=["status", "cancelled_at", "updated_at"])

        notify = list(event.registrations.filter(
            status__in=[Registration.Status.GOING, Registration.Status.WAITLIST],
        ).values_list("pk", flat=True))
        if notify and not event.has_started():
            transaction.on_commit(lambda: _send_cancellations(notify))
        return len(notify)


def _send_cancellations(ids):
    from .emails import send_event_cancelled_emails

    send_event_cancelled_emails(ids)


# Changes to these are what someone who signed up needs to hear about.
DETAILS_PEOPLE_RELY_ON = ("starts_at", "ends_at", "location", "online_url")


def notify_changes(event, changed_fields):
    """Tell everyone signed up that the time or place changed.

    Called after an admin edit. A new start time also clears the reminder
    record, so a reminder already sent for the old time is sent again for the
    new one. Returns how many people are being told.
    """
    changed = [f for f in changed_fields if f in DETAILS_PEOPLE_RELY_ON]
    if not changed or event.status != Event.Status.PUBLISHED or event.has_ended():
        return 0
    active = event.registrations.filter(
        status__in=[Registration.Status.GOING, Registration.Status.WAITLIST])
    if "starts_at" in changed:
        active.update(reminder_sent_at=None)
    ids = list(active.values_list("pk", flat=True))
    if ids:
        transaction.on_commit(lambda: _send_changes(ids, changed))
    return len(ids)


def _send_changes(ids, changed):
    from .emails import send_event_changed_emails

    send_event_changed_emails(ids, changed)


def release_places(member, only_members_events=False):
    """Give up this member's upcoming places, and move each waiting list along.

    Used when a member is paused or removed, and just before a member is
    deleted. Without it, a deleted account's registration would vanish in the
    cascade but nobody on the waiting list would ever be told the place was free.
    """
    now = timezone.now()
    registrations = Registration.objects.filter(
        member=member,
        status__in=[Registration.Status.GOING, Registration.Status.WAITLIST],
        event__starts_at__gt=now,
    )
    if only_members_events:
        registrations = registrations.filter(event__audience=Event.Audience.MEMBERS)

    # Lock events in a consistent order so two releases touching the same
    # events cannot deadlock.
    event_ids = sorted(set(registrations.values_list("event_id", flat=True)))
    released = 0
    with transaction.atomic():
        for event_id in event_ids:
            event = _locked(event_id)
            for registration in Registration.objects.filter(
                    event=event, member=member,
                    status__in=[Registration.Status.GOING, Registration.Status.WAITLIST]):
                registration.status = Registration.Status.CANCELLED
                registration.cancelled_at = now
                registration.save(update_fields=["status", "cancelled_at", "updated_at"])
                released += 1
            _settle_waiting_list(event, now)
    return released
