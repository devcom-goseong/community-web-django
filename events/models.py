"""Events people can sign up for: the weekly meeting, meetups, hackathons, demo days.

Two tables. An Event is something that happens at a time and a place. A
registration is one member's relationship to one event: they have a place, they
are on the waiting list, or they cancelled — and afterwards, whether they came
and what they did there.

That second half is what fills a member's profile. A profile lists events a
person *attended*, as marked by the leadership team, not events they merely
clicked a button for, so it stays a record worth putting on a CV.

The rules about who may register, and the handling of places and the waiting
list, live in events.services. The models only describe.
"""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from accounts.access import is_approved_member, is_staff
from accounts.validators import validate_web_url


class EventQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Events this person may know exist.

        Staff see everything, drafts included. Everyone else never sees a
        draft, and only approved members see events marked members-only.
        Cancelled events stay visible, so people who planned to come find out.
        """
        if is_staff(user):
            return self.all()
        qs = self.exclude(status=Event.Status.DRAFT)
        if not is_approved_member(user):
            qs = qs.filter(visibility=Event.Visibility.PUBLIC)
        return qs

    def with_counts(self):
        return self.annotate(
            going_total=Count(
                "registrations", filter=Q(registrations__status=Registration.Status.GOING)),
            waitlist_total=Count(
                "registrations", filter=Q(registrations__status=Registration.Status.WAITLIST)),
        )

    def upcoming(self, now=None):
        return self.filter(ends_at__gte=now or timezone.now())

    def past(self, now=None):
        return self.filter(ends_at__lt=now or timezone.now())


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft — only the leadership team can see it"
        PUBLISHED = "published", "Published"
        CANCELLED = "cancelled", "Cancelled"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Anyone can see it"
        MEMBERS = "members", "Only approved members can see it"

    class Audience(models.TextChoices):
        MEMBERS = "members", "Approved members"
        ACCOUNTS = "accounts", "Anyone with a confirmed account, including people awaiting review"

    title = models.CharField(max_length=120)
    slug = models.SlugField(
        max_length=80, unique=True, blank=True,
        help_text="The end of the event's address. Made from the title if left blank, and "
                  "fixed once the event exists, so links already shared keep working.",
    )
    activity = models.ForeignKey(
        "content.Activity", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="events",
        help_text="Which of the community's activities this is, if any. Used to group events "
                  "on profiles and on the activity's own page.",
    )
    summary = models.CharField(
        max_length=240, help_text="One or two sentences, shown in the list of events.")
    description = models.TextField(
        blank=True, default="", help_text="Optional. Anything else people should know.")

    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    location = models.CharField(
        max_length=160, blank=True, default="",
        help_text="Where to go, for example 'Engineering building, room 301'. Shown to "
                  "everyone who can see the event.",
    )
    online_url = models.URLField(
        "online link", blank=True, default="", validators=[validate_web_url],
        help_text="A video call link, if the event is online. Only shown to people who have "
                  "a place — never to people on the waiting list or to anyone else.",
    )

    capacity = models.PositiveIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1)],
        help_text="How many places. Leave blank for no limit. When it is full, new sign-ups "
                  "join a waiting list and move up automatically as places free. Raising it "
                  "gives places to the waiting list straight away; lowering it never takes a "
                  "place from anyone who already has one.",
    )
    registration_closes_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Optional. Leave blank to keep registration open until the event starts.",
    )
    visibility = models.CharField(
        max_length=10, choices=Visibility.choices, default=Visibility.PUBLIC)
    audience = models.CharField(
        "who can register", max_length=10, choices=Audience.choices, default=Audience.MEMBERS,
        help_text="'Anyone with a confirmed account' suits a newcomers' session that people "
                  "should be able to attend before their membership is reviewed.",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["starts_at", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")),
                name="event_ends_after_it_starts",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({timezone.localtime(self.starts_at):%Y-%m-%d})"

    def save(self, *args, **kwargs):
        if self.slug:
            return super().save(*args, **kwargs)
        base = (slugify(self.title) or "event")[:60].strip("-") or "event"
        stem = f"{base}-{timezone.localtime(self.starts_at):%Y-%m-%d}" if self.starts_at else base
        # Two events on the same day with the same title, created together,
        # could both pick the same slug; the unique constraint decides.
        for number in range(1, 50):
            self.slug = stem if number == 1 else f"{stem}-{number}"
            if Event.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                continue
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                if not Event.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                    self.slug = ""
                    raise
        self.slug = ""
        raise IntegrityError("could not find a free address for this event")

    def get_absolute_url(self):
        return reverse("events:detail", args=[self.slug])

    def clean(self):
        errors = {}
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "An event has to end after it starts."
        if (self.registration_closes_at and self.ends_at
                and self.registration_closes_at > self.ends_at):
            errors["registration_closes_at"] = (
                "Registration cannot stay open after the event has finished.")
        if (self.visibility == self.Visibility.MEMBERS
                and self.audience == self.Audience.ACCOUNTS):
            # People awaiting review could register, then find they cannot
            # open the event to see where it is or to cancel.
            errors["audience"] = (
                "An event only approved members can see cannot be open to people awaiting "
                "review. Make it visible to anyone, or open it to approved members only.")
        if errors:
            raise ValidationError(errors)

    # --- state -------------------------------------------------------------

    @property
    def registration_deadline(self):
        return self.registration_closes_at or self.starts_at

    def has_started(self, now=None):
        return (now or timezone.now()) >= self.starts_at

    def has_ended(self, now=None):
        return (now or timezone.now()) >= self.ends_at

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    @property
    def is_online(self):
        return bool(self.online_url)

    def visible_to(self, user):
        if is_staff(user):
            return True
        if self.status == self.Status.DRAFT:
            return False
        if self.visibility == self.Visibility.MEMBERS:
            return is_approved_member(user)
        return True

    def going_count(self):
        value = getattr(self, "going_total", None)
        if value is None:
            value = self.registrations.filter(status=Registration.Status.GOING).count()
        return value

    def waitlist_count(self):
        value = getattr(self, "waitlist_total", None)
        if value is None:
            value = self.registrations.filter(status=Registration.Status.WAITLIST).count()
        return value

    def spots_left(self):
        if self.capacity is None:
            return None
        return max(self.capacity - self.going_count(), 0)


class Registration(models.Model):
    class Status(models.TextChoices):
        GOING = "going", "Has a place"
        WAITLIST = "waitlist", "On the waiting list"
        CANCELLED = "cancelled", "Cancelled"

    class Role(models.TextChoices):
        ATTENDEE = "attendee", "Took part"
        PRESENTER = "presenter", "Presented"
        ORGANISER = "organiser", "Organised"
        HELPER = "helper", "Helped run it"

    # PROTECT: deleting an event would silently erase everyone's attendance
    # history from their profiles. Cancel an event instead of deleting it.
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="registrations")
    member = models.ForeignKey(
        "accounts.Member", on_delete=models.CASCADE, related_name="registrations")

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.GOING, db_index=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.ATTENDEE)
    attended = models.BooleanField(
        null=True, blank=True,
        help_text="Marked by the leadership team after the event. Only events marked as "
                  "attended appear on a member's profile.",
    )

    # Position on the waiting list. Reset when someone cancels and signs up
    # again, so leaving and rejoining does not keep a place in the queue.
    joined_at = models.DateTimeField(default=timezone.now)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["joined_at", "pk"]
        verbose_name = "registration"
        verbose_name_plural = "registrations"
        constraints = [
            models.UniqueConstraint(
                fields=["event", "member"], name="one_registration_per_member_per_event"),
        ]
        indexes = [
            models.Index(fields=["event", "status", "joined_at"], name="registration_queue"),
        ]

    def __str__(self):
        return f"{self.member.display_name} — {self.event.title} ({self.get_status_display()})"

    @property
    def is_active(self):
        return self.status in {self.Status.GOING, self.Status.WAITLIST}
