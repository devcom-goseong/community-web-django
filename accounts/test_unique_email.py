"""No two accounts may share an email address.

Tested at the last and strongest line of defence — the database index — which
holds however the account is made: the sign-up form, the admin, or a shell. A
blank address is exempt, because an account may legitimately have none and
several of those must not collide.
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase


class UniqueEmailTests(TestCase):
    def test_two_accounts_cannot_share_an_email_case_insensitively(self):
        User.objects.create_user("first", email="Sam@Example.com", password="pw-a")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                User.objects.create_user("second", email="sam@example.com", password="pw-b")

    def test_accounts_without_an_email_do_not_collide(self):
        User.objects.create_user("first", email="", password="pw-a")
        User.objects.create_user("second", email="", password="pw-b")
        self.assertEqual(User.objects.filter(email="").count(), 2)
