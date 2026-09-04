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
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


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

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="member"
    )

    display_name = models.CharField(
        max_length=120,
        help_text="How this person's name appears to the rest of the community.",
    )
    student = models.CharField(max_length=8, choices=Student.choices, blank=True, default="")
    student_id = models.CharField("student ID", max_length=40, blank=True, default="")
    interests = models.JSONField(default=list, blank=True)
    bio = models.TextField(
        max_length=600, blank=True, default="",
        help_text="A short introduction. Optional, and shown only to other members.",
    )
    github_url = models.URLField(blank=True, default="")
    linkedin_url = models.URLField(blank=True, default="")

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
    notes = models.TextField(blank=True, default="", help_text="Internal. Never emailed.")

    created_at = models.DateTimeField(default=timezone.now, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "member"
        verbose_name_plural = "members"

    def __str__(self):
        return f"{self.display_name} <{self.user.email}>"

    @property
    def email(self):
        return self.user.email

    @property
    def is_verified(self):
        return self.email_verified_at is not None

    @property
    def is_active_member(self):
        return self.is_verified and self.status == self.Status.ACTIVE

    def mark_verified(self):
        """Idempotent: opening the link twice is not an error."""
        if self.email_verified_at is None:
            self.email_verified_at = timezone.now()
            self.save(update_fields=["email_verified_at", "updated_at"])

    def applications(self):
        """Anything this person sent through the join form.

        Matched on the address rather than a foreign key, so an application
        sent before the account existed still shows up, and so does one sent
        afterwards without the form having to know about accounts.
        """
        from applications.models import Application

        return Application.objects.filter(email__iexact=self.user.email)
