"""Email a reminder to everyone with a place at an event that starts soon.

    python manage.py send_event_reminders            # send
    python manage.py send_event_reminders --dry-run  # say who would be emailed

Meant to run every hour; the production compose file has a scheduler service
that does exactly that. It is safe to run more often, or twice at once:

  * Each reminder is *claimed* before it is sent, with a single UPDATE that
    only succeeds if nobody has claimed it yet. Two copies of this job running
    at the same moment cannot both send the same reminder.
  * If sending fails, the claim is released, so the next run tries again.
  * Someone who signed up inside the reminder window — three hours before the
    event, say — has only just had their confirmation, so their reminder is
    marked done without sending another email.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from content.emails import send_each
from events.emails import reminder_message
from events.models import Event, Registration
from events.services import member_is_eligible


class Command(BaseCommand):
    help = "Email reminders for events starting within EVENT_REMINDER_HOURS."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=None,
                            help="Override EVENT_REMINDER_HOURS for this run.")
        parser.add_argument("--dry-run", action="store_true",
                            help="List who would be reminded, without sending or recording.")

    def handle(self, *args, hours=None, dry_run=False, **options):
        hours = settings.EVENT_REMINDER_HOURS if hours is None else hours
        now = timezone.now()
        window_end = now + timedelta(hours=hours)

        due = (Registration.objects
               .filter(status=Registration.Status.GOING,
                       reminder_sent_at__isnull=True,
                       event__status=Event.Status.PUBLISHED,
                       event__starts_at__gt=now,
                       event__starts_at__lte=window_end)
               .select_related("event", "member__user")
               .order_by("event__starts_at", "pk"))

        to_send, skipped_recent, skipped_ineligible = [], 0, 0
        for registration in due:
            if not member_is_eligible(registration.event, registration.member):
                skipped_ineligible += 1
                continue
            recent = registration.joined_at >= registration.event.starts_at - timedelta(hours=hours)
            if dry_run:
                label = "skip (signed up inside the window)" if recent else "send"
                self.stdout.write(f"{label}: {registration.member.user.email} — "
                                  f"{registration.event.title}")
                continue
            if not self._claim(registration, now):
                continue  # another run got there first
            if recent:
                skipped_recent += 1
                continue
            to_send.append(registration)

        if dry_run:
            return

        results = send_each([reminder_message(r) for r in to_send], "event reminder")
        failed = [r.pk for r, ok in zip(to_send, results, strict=True) if not ok]
        if failed:
            # Release the claim so the next run tries these again.
            Registration.objects.filter(pk__in=failed).update(reminder_sent_at=None)

        sent = len(to_send) - len(failed)
        self.stdout.write(
            f"Reminders: {sent} sent, {len(failed)} failed and will be retried, "
            f"{skipped_recent} not needed (signed up recently), "
            f"{skipped_ineligible} skipped (no longer eligible).")

    @staticmethod
    def _claim(registration, now):
        return Registration.objects.filter(
            pk=registration.pk, reminder_sent_at__isnull=True,
        ).update(reminder_sent_at=now) == 1
