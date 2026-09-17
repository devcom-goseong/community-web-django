"""Events: who can see and join them, places and the waiting list, and the jobs around them."""

import csv
import io
from datetime import datetime, timedelta

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.factories import make_member, make_staff
from accounts.models import Member
from accounts.services import change_status

from . import services
from .admin import _cell
from .ics import calendar_for
from .models import Event, Registration

TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
    "APP_URL": "https://community.example.org",
    "EVENT_REMINDER_HOURS": 24,
}

CALL = "https://meet.example.org/secret-room"


def make_event(**fields):
    start = fields.pop("starts_at", timezone.now() + timedelta(days=3))
    defaults = {
        "title": "Weekly meeting",
        "summary": "Talks, questions and plans.",
        "starts_at": start,
        "ends_at": fields.pop("ends_at", start + timedelta(hours=2)),
        "status": Event.Status.PUBLISHED,
        "visibility": Event.Visibility.PUBLIC,
        "audience": Event.Audience.MEMBERS,
    }
    defaults.update(fields)
    return Event.objects.create(**defaults)


@override_settings(**TEST_SETTINGS)
class Base(TestCase):
    def setUp(self):
        cache.clear()
        mail.outbox = []

    def register(self, event, member):
        self.client.force_login(member.user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("events:register", args=[event.slug]))

    def cancel(self, event, member):
        self.client.force_login(member.user)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("events:cancel", args=[event.slug]))

    def status_of(self, event, member):
        registration = Registration.objects.filter(event=event, member=member).first()
        return registration.status if registration else None


class VisibilityTests(Base):
    def test_drafts_are_only_for_staff(self):
        event = make_event(status=Event.Status.DRAFT, title="Secret plans")
        self.assertEqual(self.client.get(event.get_absolute_url()).status_code, 404)
        self.assertNotContains(self.client.get(reverse("events:list")), "Secret plans")

        self.client.force_login(make_member("member").user)
        self.assertEqual(self.client.get(event.get_absolute_url()).status_code, 404)

        self.client.force_login(make_staff())
        self.assertContains(self.client.get(event.get_absolute_url()), "Draft")

    def test_members_only_events_are_invisible_to_everyone_else(self):
        event = make_event(visibility=Event.Visibility.MEMBERS, title="Members dinner")
        for who in (None, make_member("pending").user, make_member("unconfirmed").user):
            with self.subTest(who=getattr(who, "email", "anonymous")):
                self.client.logout()
                if who:
                    self.client.force_login(who)
                self.assertEqual(self.client.get(event.get_absolute_url()).status_code, 404)
                self.assertNotContains(self.client.get(reverse("events:list")), "Members dinner")

        self.client.force_login(make_member("member").user)
        self.assertContains(self.client.get(reverse("events:list")), "Members dinner")

    def test_a_missing_event_and_a_members_only_one_look_identical(self):
        hidden = make_event(visibility=Event.Visibility.MEMBERS)
        missing = self.client.get("/events/no-such-event/")
        refused = self.client.get(hidden.get_absolute_url())
        self.assertEqual(missing.status_code, refused.status_code)
        self.assertNotContains(refused, hidden.title, status_code=404)

    def test_the_online_link_is_only_for_people_with_a_place(self):
        event = make_event(online_url=CALL, capacity=1)
        going, waiting, other = (make_member("member") for _ in range(3))
        self.register(event, going)
        self.register(event, waiting)

        self.client.force_login(going.user)
        self.assertContains(self.client.get(event.get_absolute_url()), CALL)
        for member in (waiting, other):
            self.client.force_login(member.user)
            self.assertNotContains(self.client.get(event.get_absolute_url()), CALL)
        self.client.logout()
        self.assertNotContains(self.client.get(event.get_absolute_url()), CALL)

    def test_names_of_people_going_respect_their_profile_setting(self):
        event = make_event()
        listed = make_member("member", name="Listed Lee", visibility=Member.Visibility.MEMBERS)
        hidden = make_member("member", name="Hidden Han")
        self.register(event, listed)
        self.register(event, hidden)

        self.client.force_login(make_member("member").user)
        response = self.client.get(event.get_absolute_url())
        self.assertContains(response, "Listed Lee")
        self.assertNotContains(response, "Hidden Han")
        self.assertContains(response, "And 1 other")

        self.client.logout()
        response = self.client.get(event.get_absolute_url())
        self.assertNotContains(response, "Listed Lee", msg_prefix="visitors only see a number")
        self.assertContains(response, "2 people")


class WhoCanRegisterTests(Base):
    def test_the_matrix(self):
        members_event = make_event(audience=Event.Audience.MEMBERS)
        open_event = make_event(audience=Event.Audience.ACCOUNTS, title="Newcomers evening")

        cases = [
            ("member", members_event, "going"),
            ("member", open_event, "going"),
            ("pending", members_event, None),
            ("pending", open_event, "going"),
            ("unconfirmed", open_event, None),
            ("paused", open_event, None),
            ("removed", open_event, None),
        ]
        for state, event, expected in cases:
            with self.subTest(state=state, event=event.title):
                member = make_member(state)
                self.register(event, member)
                self.assertEqual(self.status_of(event, member), expected)

    def test_signing_in_is_required(self):
        event = make_event()
        response = self.client.post(reverse("events:register", args=[event.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)
        self.assertFalse(Registration.objects.exists())

    def test_a_staff_account_without_a_member_row_is_refused_cleanly(self):
        event = make_event()
        self.client.force_login(make_staff())
        response = self.client.post(reverse("events:register", args=[event.slug]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not a member account")

    def test_no_registering_for_something_cancelled_started_or_closed(self):
        now = timezone.now()
        cases = {
            "cancelled": make_event(status=Event.Status.CANCELLED),
            "started": make_event(starts_at=now - timedelta(minutes=5),
                                  ends_at=now + timedelta(hours=1)),
            "closed": make_event(registration_closes_at=now - timedelta(hours=1)),
        }
        for label, event in cases.items():
            with self.subTest(case=label):
                member = make_member("member")
                self.register(event, member)
                self.assertIsNone(self.status_of(event, member))

    def test_register_only_accepts_post(self):
        event = make_event()
        self.client.force_login(make_member("member").user)
        self.assertEqual(
            self.client.get(reverse("events:register", args=[event.slug])).status_code, 405)


class PlacesAndWaitingListTests(Base):
    def test_full_events_have_a_waiting_list_in_order(self):
        event = make_event(capacity=2)
        a, b, c, d = (make_member("member") for _ in range(4))
        for member in (a, b, c, d):
            self.register(event, member)
        self.assertEqual([self.status_of(event, m) for m in (a, b, c, d)],
                         ["going", "going", "waitlist", "waitlist"])

    def test_cancelling_a_place_gives_it_to_the_first_person_waiting_and_emails_them(self):
        event = make_event(capacity=1)
        first, second, third = (make_member("member") for _ in range(3))
        for member in (first, second, third):
            self.register(event, member)
        mail.outbox = []

        self.cancel(event, first)
        self.assertEqual(self.status_of(event, first), "cancelled")
        self.assertEqual(self.status_of(event, second), "going")
        self.assertEqual(self.status_of(event, third), "waitlist")
        self.assertEqual([m.to for m in mail.outbox], [[second.email]])
        self.assertIn("A place opened up", mail.outbox[0].subject)

    def test_leaving_the_waiting_list_promotes_nobody(self):
        event = make_event(capacity=1)
        going, waiting = make_member("member"), make_member("member")
        self.register(event, going)
        self.register(event, waiting)
        mail.outbox = []
        self.cancel(event, waiting)
        self.assertEqual(self.status_of(event, going), "going")
        self.assertEqual(mail.outbox, [])

    def test_cancelling_and_signing_up_again_goes_to_the_back_of_the_queue(self):
        event = make_event(capacity=1)
        holder, early, late = (make_member("member") for _ in range(3))
        self.register(event, holder)
        self.register(event, early)
        self.register(event, late)
        self.cancel(event, early)
        self.register(event, early)  # rejoins behind `late`

        self.cancel(event, holder)
        self.assertEqual(self.status_of(event, late), "going")
        self.assertEqual(self.status_of(event, early), "waitlist")
        self.assertEqual(Registration.objects.filter(event=event, member=early).count(), 1)

    def test_a_new_sign_up_cannot_jump_people_already_waiting(self):
        event = make_event(capacity=1)
        holder, waiting = make_member("member"), make_member("member")
        self.register(event, holder)
        self.register(event, waiting)
        # A place frees without the waiting list being settled, as a direct
        # database change or an interrupted request could leave it.
        Registration.objects.filter(event=event, member=holder).update(status="cancelled")

        newcomer = make_member("member")
        self.register(event, newcomer)
        self.assertEqual(self.status_of(event, waiting), "going")
        self.assertEqual(self.status_of(event, newcomer), "waitlist")

    def test_registering_twice_changes_nothing(self):
        event = make_event()
        member = make_member("member")
        self.register(event, member)
        mail.outbox = []
        self.register(event, member)
        self.assertEqual(Registration.objects.filter(event=event).count(), 1)
        self.assertEqual(mail.outbox, [], "no second confirmation")

    def test_someone_paused_while_waiting_is_skipped_not_promoted(self):
        event = make_event(capacity=1)
        holder, paused, next_in_line = (make_member("member") for _ in range(3))
        for member in (holder, paused, next_in_line):
            self.register(event, member)
        Member.objects.filter(pk=paused.pk).update(status=Member.Status.PAUSED)

        self.cancel(event, holder)
        self.assertEqual(self.status_of(event, paused), "cancelled")
        self.assertEqual(self.status_of(event, next_in_line), "going")

    def test_no_cancelling_after_the_start(self):
        now = timezone.now()
        event = make_event(starts_at=now + timedelta(hours=1))
        member = make_member("member")
        self.register(event, member)
        Event.objects.filter(pk=event.pk).update(starts_at=now - timedelta(minutes=1),
                                                 ends_at=now + timedelta(hours=1))
        self.cancel(event, member)
        self.assertEqual(self.status_of(event, member), "going")

    def test_the_confirmation_email_has_a_calendar_file_and_the_call_link(self):
        event = make_event(online_url=CALL)
        member = make_member("member")
        self.register(event, member)
        message = mail.outbox[0]
        self.assertIn("You have a place", message.subject)
        self.assertIn(CALL, message.body)
        self.assertEqual(message.attachments[0][2], "text/calendar")

    def test_the_waiting_list_email_does_not_have_the_call_link(self):
        event = make_event(online_url=CALL, capacity=1)
        self.register(event, make_member("member"))
        waiting = make_member("member")
        mail.outbox = []
        self.register(event, waiting)
        self.assertIn("waiting list", mail.outbox[0].subject)
        self.assertNotIn(CALL, mail.outbox[0].body)


class MemberChangesTests(Base):
    def test_pausing_a_member_frees_their_places(self):
        event = make_event(capacity=1)
        holder, waiting = make_member("member"), make_member("member")
        self.register(event, holder)
        self.register(event, waiting)
        with self.captureOnCommitCallbacks(execute=True):
            change_status(holder, Member.Status.PAUSED)
        self.assertEqual(self.status_of(event, holder), "cancelled")
        self.assertEqual(self.status_of(event, waiting), "going")

    def test_going_back_to_pending_only_frees_members_only_places(self):
        members_event = make_event(audience=Event.Audience.MEMBERS)
        open_event = make_event(audience=Event.Audience.ACCOUNTS)
        member = make_member("member")
        self.register(members_event, member)
        self.register(open_event, member)
        change_status(member, Member.Status.PENDING)
        self.assertEqual(self.status_of(members_event, member), "cancelled")
        self.assertEqual(self.status_of(open_event, member), "going")

    def test_deleting_an_account_gives_its_place_to_the_waiting_list(self):
        event = make_event(capacity=1)
        holder, waiting = make_member("member"), make_member("member")
        self.register(event, holder)
        self.register(event, waiting)
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            holder.user.delete()
        self.assertEqual(self.status_of(event, waiting), "going")
        self.assertEqual([m.to for m in mail.outbox], [[waiting.email]])

    def test_closing_an_account_through_the_site_does_the_same(self):
        event = make_event(capacity=1)
        holder, waiting = make_member("member"), make_member("member")
        self.register(event, holder)
        self.register(event, waiting)
        self.client.force_login(holder.user)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("accounts:close"), {"password": "correct-horse-battery"})
        self.assertEqual(self.status_of(event, waiting), "going")

    def test_an_event_with_registrations_cannot_be_deleted(self):
        event = make_event()
        self.register(event, make_member("member"))
        with self.assertRaises(ProtectedError):
            event.delete()


class AdminTests(Base):
    def setUp(self):
        super().setUp()
        self.admin = make_staff()
        self.admin.is_superuser = True
        self.admin.save()

    def action(self, name, *events):
        self.client.force_login(self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse("admin:events_event_changelist"), {
                "action": name, "_selected_action": [str(e.pk) for e in events],
                "index": "0", "select_across": "0",
            })

    def test_cancelling_an_event_tells_everyone_signed_up(self):
        event = make_event(capacity=1)
        going, waiting = make_member("member"), make_member("member")
        self.register(event, going)
        self.register(event, waiting)
        mail.outbox = []
        self.action("cancel_and_notify", event)
        event.refresh_from_db()
        self.assertEqual(event.status, Event.Status.CANCELLED)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([going.email, waiting.email]))

        mail.outbox = []
        self.action("cancel_and_notify", event)
        self.assertEqual(mail.outbox, [], "cancelling twice does not email twice")

    def test_marking_attendance_only_touches_finished_events(self):
        now = timezone.now()
        member = make_member("member")
        past = make_event(starts_at=now + timedelta(hours=1))
        self.register(past, member)
        Event.objects.filter(pk=past.pk).update(starts_at=now - timedelta(days=2),
                                                ends_at=now - timedelta(days=2, hours=-2))
        future = make_event()
        self.register(future, member)

        self.action("mark_going_as_attended", past, future)
        self.assertTrue(Registration.objects.get(event=past, member=member).attended)
        self.assertIsNone(Registration.objects.get(event=future, member=member).attended)

    def test_the_attendee_export_is_safe_to_open_in_a_spreadsheet(self):
        event = make_event()
        self.register(event, make_member("member", name="=HYPERLINK(\"http://evil\")"))
        self.register(event, make_member("member", name="김민수"))
        response = self.action("export_attendees", event)
        body = response.content.decode("utf-8")
        self.assertTrue(body.startswith("﻿"), "a BOM, so Excel reads Korean correctly")
        rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
        names = [row[2] for row in rows[1:]]
        self.assertIn("'=HYPERLINK(\"http://evil\")", names)
        self.assertIn("김민수", names)

    def test_cell_escaping(self):
        for dangerous in ("=1+1", "+1", "-1", "@SUM(A1)"):
            self.assertTrue(_cell(dangerous).startswith("'"))
        self.assertEqual(_cell("Plain name"), "Plain name")

    def test_raising_the_capacity_moves_the_waiting_list(self):
        event = make_event(capacity=1)
        going, waiting = make_member("member"), make_member("member")
        self.register(event, going)
        self.register(event, waiting)
        Event.objects.filter(pk=event.pk).update(capacity=2)
        with self.captureOnCommitCallbacks(execute=True):
            services.settle_waiting_list(event)
        self.assertEqual(self.status_of(event, waiting), "going")

    def test_the_address_cannot_change_once_the_event_exists(self):
        from django.contrib.admin.sites import site

        from .admin import EventAdmin

        admin = EventAdmin(Event, site)
        event = make_event()
        self.assertIn("slug", admin.get_readonly_fields(None, event))
        self.assertNotIn("slug", admin.get_readonly_fields(None, None))


class CalendarTests(Base):
    def test_the_file_is_valid_and_in_utc(self):
        start = timezone.make_aware(datetime(2026, 10, 1, 18, 0))  # 18:00 KST
        event = make_event(title="Talks, pizza; demos", starts_at=start,
                           ends_at=start + timedelta(hours=2), location="Room 301")
        text = calendar_for(event)
        self.assertTrue(text.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(text.endswith("END:VCALENDAR\r\n"))
        self.assertIn("DTSTART:20261001T090000Z", text)
        self.assertIn("SUMMARY:Talks\\, pizza\\; demos", text)
        self.assertIn(f"UID:event-{event.pk}@community.example.org", text)
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_long_korean_lines_fold_without_breaking_characters(self):
        # 119 characters, under the 120 the column allows. PostgreSQL enforces
        # that length and SQLite does not, so a longer title here would pass
        # locally and fail in CI.
        title = "한국어 제목 " * 17
        event = make_event(title=title)
        text = calendar_for(event)
        unfolded = text.replace("\r\n ", "")
        self.assertIn("SUMMARY:" + title, unfolded)
        for line in text.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

    def test_the_download_only_includes_the_call_for_people_with_a_place(self):
        event = make_event(online_url=CALL)
        member = make_member("member")
        url = reverse("events:calendar", args=[event.slug])
        self.assertNotIn(CALL, self.client.get(url).content.decode())
        self.register(event, member)
        self.client.force_login(member.user)
        response = self.client.get(url)
        self.assertEqual(response["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn(CALL, response.content.decode())

    def test_a_cancelled_event_says_so(self):
        event = make_event(status=Event.Status.CANCELLED)
        self.assertIn("STATUS:CANCELLED", calendar_for(event))


class ReminderTests(Base):
    def run_job(self, **kwargs):
        out = io.StringIO()
        call_command("send_event_reminders", stdout=out, **kwargs)
        return out.getvalue()

    def signed_up_earlier(self, event, member, hours_before=48):
        registration = Registration.objects.create(event=event, member=member, status="going")
        Registration.objects.filter(pk=registration.pk).update(
            joined_at=event.starts_at - timedelta(hours=hours_before))
        return registration

    def test_it_sends_once_and_only_once(self):
        event = make_event(starts_at=timezone.now() + timedelta(hours=20))
        member = make_member("member")
        self.signed_up_earlier(event, member)
        self.run_job()
        self.run_job()
        self.assertEqual([m.to for m in mail.outbox], [[member.email]])
        self.assertIn("Reminder", mail.outbox[0].subject)

    def test_it_skips_what_it_should(self):
        now = timezone.now()
        soon = make_event(starts_at=now + timedelta(hours=10))
        later = make_event(starts_at=now + timedelta(days=5))
        cancelled = make_event(starts_at=now + timedelta(hours=10), status=Event.Status.CANCELLED)
        self.signed_up_earlier(later, make_member("member"), hours_before=200)
        self.signed_up_earlier(cancelled, make_member("member"))
        paused = make_member("member")
        self.signed_up_earlier(soon, paused)
        Member.objects.filter(pk=paused.pk).update(status=Member.Status.PAUSED)
        waiting = make_member("member")
        Registration.objects.create(event=soon, member=waiting, status="waitlist")

        self.run_job()
        self.assertEqual(mail.outbox, [])

    def test_someone_who_just_signed_up_is_not_reminded_straight_after_their_confirmation(self):
        event = make_event(starts_at=timezone.now() + timedelta(hours=5))
        Registration.objects.create(event=event, member=make_member("member"), status="going")
        output = self.run_job()
        self.assertEqual(mail.outbox, [])
        self.assertIn("1 not needed", output)
        self.run_job()
        self.assertEqual(mail.outbox, [], "and it stays marked done")

    def test_a_failed_send_is_retried_next_time(self):
        from unittest import mock

        event = make_event(starts_at=timezone.now() + timedelta(hours=20))
        registration = self.signed_up_earlier(event, make_member("member"))
        with mock.patch("django.core.mail.backends.locmem.EmailBackend.send_messages",
                        side_effect=OSError("smtp down")):
            self.run_job()
        registration.refresh_from_db()
        self.assertIsNone(registration.reminder_sent_at, "claim released after the failure")

        self.run_job()
        self.assertEqual(len(mail.outbox), 1)

    def test_dry_run_sends_and_records_nothing(self):
        event = make_event(starts_at=timezone.now() + timedelta(hours=20))
        registration = self.signed_up_earlier(event, make_member("member"))
        output = self.run_job(dry_run=True)
        self.assertIn("send:", output)
        registration.refresh_from_db()
        self.assertIsNone(registration.reminder_sent_at)
        self.assertEqual(mail.outbox, [])


class ModelTests(Base):
    def test_an_event_must_end_after_it_starts(self):
        from django.core.exceptions import ValidationError

        start = timezone.now() + timedelta(days=1)
        event = Event(title="Backwards", summary="x", starts_at=start, ends_at=start)
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_slugs_are_unique_and_readable(self):
        start = timezone.now() + timedelta(days=1)
        first = make_event(title="Hack night", starts_at=start)
        second = make_event(title="Hack night", starts_at=start)
        self.assertTrue(first.slug.startswith("hack-night-"))
        self.assertNotEqual(first.slug, second.slug)

    def test_the_home_page_mentions_the_next_public_event(self):
        make_event(title="Open evening")
        make_event(title="Members supper", visibility=Event.Visibility.MEMBERS,
                   starts_at=timezone.now() + timedelta(days=1))
        response = self.client.get(reverse("content:home"))
        self.assertContains(response, "Open evening")
        self.assertNotContains(response, "Members supper")


class ChangesAndLeaksTests(Base):
    def test_moving_an_event_tells_everyone_signed_up_and_resets_their_reminder(self):
        event = make_event(capacity=1, starts_at=timezone.now() + timedelta(hours=20))
        going, waiting = make_member("member"), make_member("member")
        self.register(event, going)
        self.register(event, waiting)
        Registration.objects.filter(event=event).update(reminder_sent_at=timezone.now())
        mail.outbox = []

        event.starts_at += timedelta(days=1)
        event.ends_at += timedelta(days=1)
        event.save()
        with self.captureOnCommitCallbacks(execute=True):
            told = services.notify_changes(event, ["starts_at", "ends_at"])

        self.assertEqual(told, 2)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), sorted([going.email, waiting.email]))
        self.assertTrue(all("time" in m.subject.lower() or "Changed" in m.subject for m in mail.outbox))
        self.assertFalse(Registration.objects.filter(event=event, reminder_sent_at__isnull=False).exists(),
                         "a reminder for the old time is sent again for the new one")

    def test_the_new_call_link_only_goes_to_people_with_a_place(self):
        event = make_event(capacity=1)
        going, waiting = make_member("member"), make_member("member")
        self.register(event, going)
        self.register(event, waiting)
        mail.outbox = []
        event.online_url = CALL
        event.save()
        with self.captureOnCommitCallbacks(execute=True):
            services.notify_changes(event, ["online_url"])
        by_person = {m.to[0]: m.body for m in mail.outbox}
        self.assertIn(CALL, by_person[going.email])
        self.assertNotIn(CALL, by_person[waiting.email])

    def test_editing_something_nobody_relies_on_emails_nobody(self):
        event = make_event()
        self.register(event, make_member("member"))
        mail.outbox = []
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(services.notify_changes(event, ["title", "summary"]), 0)
        self.assertEqual(mail.outbox, [])

    def test_members_only_events_cannot_be_opened_to_people_awaiting_review(self):
        from django.core.exceptions import ValidationError

        start = timezone.now() + timedelta(days=1)
        event = Event(title="Contradiction", summary="x", starts_at=start,
                      ends_at=start + timedelta(hours=1),
                      visibility=Event.Visibility.MEMBERS, audience=Event.Audience.ACCOUNTS)
        with self.assertRaises(ValidationError):
            event.full_clean()

    def test_a_public_profile_does_not_reveal_members_only_event_titles(self):
        member = make_member("member", visibility=Member.Visibility.PUBLIC)
        secret = make_event(title="Private strategy night", visibility=Event.Visibility.MEMBERS)
        open_one = make_event(title="Open workshop")
        for event in (secret, open_one):
            Registration.objects.create(event=event, member=member, status="going", attended=True)

        self.client.logout()
        response = self.client.get(member.get_absolute_url())
        self.assertContains(response, "Open workshop")
        self.assertNotContains(response, "Private strategy night")

        self.client.force_login(make_member("member").user)
        self.assertContains(self.client.get(member.get_absolute_url()), "Private strategy night")
