"""Test helpers for making people at every stage of the way in.

Not named test_*.py, so the test runner does not try to collect it.
"""

from itertools import count

from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Member

UserModel = get_user_model()
_numbers = count(1)

PASSWORD = "correct-horse-battery"


def make_member(state="member", name=None, visibility=Member.Visibility.HIDDEN, **fields):
    """A user with a Member row, in one of these states:

    unconfirmed   signed up, address not confirmed
    pending       confirmed, awaiting review
    member        confirmed and approved
    paused        confirmed, membership paused
    removed       confirmed, removed
    """
    number = next(_numbers)
    email = fields.pop("email", f"person{number}@example.org")
    user = UserModel.objects.create_user(username=email, email=email, password=PASSWORD)
    now = timezone.now()
    status = {
        "unconfirmed": Member.Status.PENDING,
        "pending": Member.Status.PENDING,
        "member": Member.Status.ACTIVE,
        "paused": Member.Status.PAUSED,
        "removed": Member.Status.REMOVED,
    }[state]
    return Member.objects.create(
        user=user,
        display_name=name or f"Person {number}",
        status=status,
        email_verified_at=None if state == "unconfirmed" else now,
        approved_at=now if status == Member.Status.ACTIVE else None,
        profile_visibility=visibility,
        accepted_documents=True,
        accepted_at=now,
        **fields,
    )


def make_staff(with_member=False):
    number = next(_numbers)
    email = f"staff{number}@example.org"
    user = UserModel.objects.create_user(
        username=email, email=email, password=PASSWORD, is_staff=True)
    if with_member:
        Member.objects.create(user=user, display_name=f"Staff {number}",
                              status=Member.Status.ACTIVE, email_verified_at=timezone.now())
    return user
