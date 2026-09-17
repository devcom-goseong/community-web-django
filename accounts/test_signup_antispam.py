"""The sign-up form's quiet bot defences.

These check the two things the honeypot and the timestamp promise: an automated
post is turned away and makes nothing, and an ordinary post — including one that
never carried a timestamp at all — is left alone.
"""

from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from content.models import InterestArea

from . import antispam
from .antispam import HONEYPOT_FIELD, TIMESTAMP_FIELD, new_timestamp

UserModel = get_user_model()

# The same production posture the rest of the account tests run under: TLS
# redirect off so requests reach the view, with a local cache and mail backend.
TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    "EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend",
}

GOOD = {
    "display_name": "Sam Park",
    "email": "sam@example.org",
    "student": "yes",
    "student_id": "20260001",
    "password1": "correct-horse-battery",
    "password2": "correct-horse-battery",
    "accepted_documents": "on",
}


def _signed(seconds_ago):
    """A validly signed timestamp issued ``seconds_ago`` in the past."""
    import time
    return signing.Signer(salt=antispam._SALT).sign(str(int(time.time()) - seconds_ago))


@override_settings(**TEST_SETTINGS)
class SignupAntispamTests(TestCase):
    def setUp(self):
        cache.clear()
        InterestArea.objects.create(name="Programming", order=0)
        mail.outbox = []

    def post(self, **overrides):
        return self.client.post(reverse("accounts:signup"), {**GOOD, **overrides})

    def _no_account(self):
        self.assertFalse(UserModel.objects.filter(email="sam@example.org").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_a_filled_honeypot_is_turned_away_and_makes_nothing(self):
        response = self.post(**{HONEYPOT_FIELD: "Acme Marketing LLC"})
        self.assertRedirects(response, reverse("accounts:login"))
        self._no_account()

    def test_a_post_within_three_seconds_is_turned_away(self):
        response = self.post(**{TIMESTAMP_FIELD: new_timestamp()})
        self.assertRedirects(response, reverse("accounts:login"))
        self._no_account()

    def test_a_plain_post_with_no_timestamp_still_creates_the_account(self):
        response = self.post()
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertTrue(UserModel.objects.filter(email="sam@example.org").exists())

    def test_an_unhurried_post_that_carries_a_timestamp_is_accepted(self):
        response = self.post(**{TIMESTAMP_FIELD: _signed(30)})
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertTrue(UserModel.objects.filter(email="sam@example.org").exists())

    def test_a_tampered_timestamp_is_ignored_not_trusted(self):
        # A forged token is not a valid signature, so it cannot be used to look
        # "old enough"; the post is judged as if it carried no timestamp.
        response = self.post(**{TIMESTAMP_FIELD: "999999999:forged"})
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertTrue(UserModel.objects.filter(email="sam@example.org").exists())
