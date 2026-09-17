"""Member accounts.

The join form stays the front door: anyone can send a message or apply
without an account. An account is the thing that comes *after* — it is how a
member signs in, keeps their own details current, and sees where their
application got to.

Why `auth.User` rather than a custom user model: the project already has
migrations against the stock user table, and swapping `AUTH_USER_MODEL` after
that point is a rewrite rather than a change. Everything the community needs
that the stock model lacks lives on `Member` instead, which is a one-to-one
row created alongside every account.

Email is the identity. `User.username` is set to the address so the stock
admin and password reset keep working, and `accounts.backends.EmailBackend`
does the sign-in lookup case-insensitively.

A profile is private until its owner decides otherwise. Nothing about a member
is shown to anyone but the member and the leadership team unless the member
chooses a wider visibility, and even then the email address, the student ID and
whether they are a student are never shown.
"""

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.urls import reverse
from django.utils import timezone

from .validators import (
    generate_handle,
    validate_github_url,
    validate_handle,
    validate_linkedin_url,
    validate_web_url,
)

MAX_PROJECTS = 8


class Member(models.Model):
    """The community-facing half of an account."""

    class Student(models.TextChoices):
        YES = "yes", "Yes"
        NO = "no", "No"
        SOON = "soon", "Starting soon"
        UNKNOWN = "", "Not answered"

    class Status(models.TextChoices):
        PENDING = "pending", "Awaiting review"
        ACTIVE = "active", "Member"
        PAUSED = "paused", "Paused"
        REMOVED = "removed", "Removed"

    class Visibility(models.TextChoices):
        # The leadership team can see every profile whatever this says, so they
        # can look after the community. The label says so, rather than letting
        # "Only me" be quietly untrue.
        HIDDEN = "hidden", "Only me (and the leadership team)"
        MEMBERS = "members", "Members of the community"
        PUBLIC = "public", "Anyone with the link"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member"
    )

    display_name = models.CharField(
        max_length=120,
        help_text="How this person's name appears to the rest of the community.",
    )
    # blank=True so forms that do not show the handle (sign-up, the admin's
    # add screen) are not refused; save() fills an empty one in.
    handle = models.SlugField(
        max_length=30,
        unique=True,
        blank=True,
        validators=[validate_handle],
        help_text="The end of the profile address, /members/<handle>/. Generated from the "
                  "name; the member can change it.",
    )
    profile_visibility = models.CharField(
        max_length=10,
        choices=Visibility.choices,
        default=Visibility.HIDDEN,
        help_text="Who can see the profile page. 'Members' and 'Anyone with the link' also "
                  "list the member in the members directory.",
    )
    student = models.CharField(max_length=8, choices=Student.choices, blank=True, default="")
    student_id = models.CharField("student ID", max_length=40, blank=True, default="")
    interests = models.JSONField(default=list, blank=True)
    bio = models.TextField(
        max_length=600, blank=True, default="",
        help_text="A short introduction. Shown on the profile, to whoever the profile "
                  "visibility allows.",
    )
    github_url = models.URLField(blank=True, default="", validators=[validate_github_url])
    linkedin_url = models.URLField(blank=True, default="", validators=[validate_linkedin_url])

    # The record that the rules, terms and privacy notice were accepted, kept
    # for the same reason it is kept on an application: it is the evidence.
    accepted_documents = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)

    # An address is unverified until the signed link in the welcome email is
    # opened. An unverified account can sign in and correct its own details,
    # but is not treated as a real member anywhere else.
    email_verified_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    approved_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When they first became a member. Set automatically on approval.",
    )
    notes = models.TextField(blank=True, default="", help_text="Internal. Never emailed.")

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "member"
        verbose_name_plural = "members"

    def __str__(self):
        return f"{self.display_name} <{self.user.email}>"

    def save(self, *args, **kwargs):
        if self.handle:
            return super().save(*args, **kwargs)

        # A generated handle is checked for uniqueness before saving, but two
        # people with the same name signing up at the same moment can both be
        # told "sam-park" is free. The database's unique constraint catches the
        # second, which then gets a suffixed handle instead of an error page.
        for attempt in range(3):
            self.handle = generate_handle(
                self.display_name if attempt == 0 else "", self._handle_taken)
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                clash = Member.objects.filter(handle=self.handle).exclude(pk=self.pk).exists()
                self.handle = ""
                if not clash:
                    raise  # a different constraint failed; do not hide it
        raise IntegrityError("could not allocate a unique handle")

    def get_absolute_url(self):
        return reverse("members:profile", args=[self.handle])

    @property
    def email(self):
        return self.user.email

    @property
    def is_verified(self):
        return self.email_verified_at is not None

    @property
    def is_active_member(self):
        return self.is_verified and self.status == self.Status.ACTIVE

    @property
    def is_listed(self):
        """Whether this member appears in the members directory."""
        return (
            self.is_active_member
            and self.user.is_active
            and self.profile_visibility in {self.Visibility.MEMBERS, self.Visibility.PUBLIC}
        )

    @property
    def initials(self):
        words = [w for w in (self.display_name or "").split() if w]
        letters = "".join(w[0] for w in words[:2]) or "?"
        return letters.upper()

    def profile_visible_to(self, user):
        """Whether `user` may see this member's profile page.

        The owner and the leadership team always can. Everyone else only sees
        a profile that belongs to an approved, active member and whose chosen
        visibility includes them, so a paused or removed member's page
        disappears for everyone else at once, whatever it was set to.
        """
        from .access import is_approved_member, is_staff

        if getattr(user, "is_authenticated", False) and (
                user.pk == self.user_id or is_staff(user)):
            return True
        if not (self.is_active_member and self.user.is_active):
            return False
        if self.profile_visibility == self.Visibility.PUBLIC:
            return True
        if self.profile_visibility == self.Visibility.MEMBERS:
            return is_approved_member(user)
        return False

    def _handle_taken(self, candidate):
        return Member.objects.filter(handle__iexact=candidate).exclude(pk=self.pk).exists()

    def mark_verified(self):
        """Idempotent: opening the link twice is not an error.

        Returns True only the first time, so anything that should happen once
        on confirmation happens once.
        """
        if self.email_verified_at is not None:
            return False
        self.email_verified_at = timezone.now()
        self.save(update_fields=["email_verified_at", "updated_at"])
        return True

    def applications(self):
        """Anything this person sent through the join form.

        Matched on the address rather than a foreign key, so an application
        sent before the account existed still shows up, and so does one sent
        afterwards without the form having to know about accounts.
        """
        from applications.models import Application

        return Application.objects.filter(email__iexact=self.user.email)


class MemberProject(models.Model):
    """Something a member has made, listed on their own profile.

    Not a project board: nobody else can join or edit these. It is the part of
    a profile that makes it worth putting on a CV.
    """

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name="projects")
    title = models.CharField(max_length=80)
    url = models.URLField(
        "link", blank=True, default="", validators=[validate_web_url],
        help_text="Optional. Where people can see it: a repository, a demo, a write-up.",
    )
    description = models.CharField(
        max_length=200, blank=True, default="", help_text="Optional. One sentence.")
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["order", "pk"]
        verbose_name = "project"
        verbose_name_plural = "projects"

    def __str__(self):
        return self.title
