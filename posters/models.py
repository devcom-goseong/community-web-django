"""Talk posters: a link for a presenter, what they send back, and the poster made from it.

The team used to collect each presenter's details with a Google Form and lay
the poster out by hand before every weekly meeting. Now an admin makes a link
here and sends it; the presenter fills in their talk and a photo without
needing an account; the site draws the poster; and an admin checks it before it
appears on an event page.

One row follows a talk through that, so its status is the whole story:

  waiting    the link has been made and sent; nobody has filled it in yet
  submitted  the presenter has filled it in and the poster is drawn; it is
             waiting for an admin, and nobody outside the team can see it
  approved   an admin has attached it to an event, and the event's page shows it

The admin, not the presenter, sets the date, time and place, so a poster always
matches the schedule. The link works once: it closes when the presenter sends
the form, or when it expires, whichever comes first.
"""

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

LINK_DAYS = 7


def new_token():
    return secrets.token_urlsafe(24)


def link_expiry():
    return timezone.now() + timedelta(days=LINK_DAYS)


class Platform(models.TextChoices):
    GOOGLE_MEET = "meet", "Google Meet"
    ZOOM = "zoom", "Zoom"
    DISCORD = "discord", "Discord"
    IN_PERSON = "in_person", "In person"


class TalkPosterQuerySet(models.QuerySet):
    def approved(self):
        return self.filter(status=TalkPoster.Status.APPROVED).exclude(poster="")


class TalkPoster(models.Model):
    class Status(models.TextChoices):
        WAITING = "waiting", "Link sent, waiting for the presenter"
        SUBMITTED = "submitted", "Filled in, waiting for review"
        APPROVED = "approved", "Approved, on the event page"

    token = models.CharField(max_length=64, unique=True, default=new_token, editable=False)
    link_expires_at = models.DateTimeField(
        "link works until", default=link_expiry,
        help_text=f"The link stops working at this time, or as soon as the presenter sends the "
                  f"form. New links last {LINK_DAYS} days.",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.WAITING, db_index=True)

    # Set by the admin who makes the link. The presenter sees these but cannot change them.
    event = models.ForeignKey(
        "events.Event", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="talk_posters",
        help_text="Optional. The event this talk is for. Leave it blank to create the event "
                  "from the poster when you approve it.",
    )
    label = models.CharField(
        max_length=30, default="Weekly meeting",
        help_text="The blue label above the title, for example 'Weekly meeting' or 'Workshop'.")
    starts_at = models.DateTimeField("starts")
    ends_at = models.DateTimeField("ends")
    platform = models.CharField(
        "where", max_length=10, choices=Platform.choices, default=Platform.GOOGLE_MEET,
        help_text="Online talks show the platform's name and '(Virtual)' on the poster.")
    place = models.CharField(
        "room", max_length=60, blank=True, default="",
        help_text="In person only. For example 'Engineering building, room 301'.")
    place_detail = models.CharField(
        "second line", max_length=60, blank=True, default="",
        help_text="In person only, optional. Shown in brackets under the room, for example "
                  "'Kyungdong University'.")

    # Filled in by the presenter.
    title = models.CharField(max_length=70, blank=True, default="")
    summary = models.CharField(
        "short description", max_length=180, blank=True, default="",
        help_text="Shown under the title on the poster, and in the list of events.")
    about = models.CharField(
        "about the talk", max_length=230, blank=True, default="",
        help_text="Shown in the 'About the talk' box on the poster.")
    speaker_name = models.CharField("speaker's name", max_length=50, blank=True, default="")
    speaker_tag = models.CharField(
        "speaker's role", max_length=30, blank=True, default="",
        help_text="The blue badge under the name, for example 'KDU Alumni'.")
    photo = models.ImageField(
        upload_to="posters/photos/", blank=True,
        help_text="The presenter's photo. Kept private: only the poster made from it is shown.")
    submitted_at = models.DateTimeField(null=True, blank=True)

    poster = models.ImageField(upload_to="posters/", blank=True, editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+", editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    objects = TalkPosterQuerySet.as_manager()

    class Meta:
        ordering = ["-starts_at", "-pk"]
        verbose_name = "talk poster"
        verbose_name_plural = "talk posters"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="talk_poster_ends_after_it_starts",
            ),
        ]

    def __str__(self):
        who = self.speaker_name or "presenter not filled in yet"
        return f"{self.title or 'Untitled talk'} — {who}"

    def get_absolute_url(self):
        return reverse("posters:present", args=[self.token])

    @property
    def is_online(self):
        return self.platform != Platform.IN_PERSON

    def place_lines(self):
        """The two lines of the place on the poster: 'Zoom' and 'Virtual', or the room and its detail."""
        if self.is_online:
            return self.get_platform_display(), "Virtual"
        return self.place, self.place_detail

    def link_is_open(self, now=None):
        return self.status == self.Status.WAITING and (now or timezone.now()) < self.link_expires_at

    @property
    def is_filled_in(self):
        return bool(self.title and self.summary and self.about and self.speaker_name
                    and self.speaker_tag and self.photo)

    def give_new_link(self):
        """A fresh link for the presenter to fill the form in again, keeping what they sent before."""
        self.token = new_token()
        self.link_expires_at = link_expiry()
        self.status = self.Status.WAITING
        self.approved_at = None
        self.approved_by = None
