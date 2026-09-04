from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from content.models import InterestArea

from .emails import SALT, make_token
from .models import Member

UserModel = get_user_model()

# CI runs with DEBUG off and SECURE_SSL_REDIRECT on, which is the point: it
# checks the production posture of the settings module. The consequence is that
# the test client's http:// requests are answered with a 301 to https:// and
# never reach a view, so it has to be off for tests that make requests. The
# cache and the mail backend are pinned here rather than left to the
# environment, so the suite behaves the same whoever runs it.
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


@override_settings(**TEST_SETTINGS)
class SignUpTests(TestCase):
    def setUp(self):
        cache.clear()
        InterestArea.objects.create(name="Programming", order=0)
        mail.outbox = []

    def post(self, **overrides):
        data = {**GOOD, **overrides}
        return self.client.post(reverse("accounts:signup"), data)

    def test_signing_up_creates_a_user_and_a_member(self):
        response = self.post()
        self.assertRedirects(response, reverse("accounts:dashboard"))

        user = UserModel.objects.get(email="sam@example.org")
        self.assertEqual(user.username, "sam@example.org")
        self.assertEqual(user.member.display_name, "Sam Park")
        self.assertEqual(user.member.status, Member.Status.PENDING)

    def test_the_password_is_hashed_not_stored(self):
        self.post()
        user = UserModel.objects.get(email="sam@example.org")
        self.assertNotIn("correct-horse-battery", user.password)
        self.assertTrue(user.check_password("correct-horse-battery"))

    def test_the_consent_box_actually_stops_the_submission(self):
        response = self.client.post(reverse("accounts:signup"),
                                    {k: v for k, v in GOOD.items() if k != "accepted_documents"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(UserModel.objects.filter(email="sam@example.org").exists())

    def test_accepting_is_recorded_with_a_timestamp(self):
        self.post()
        member = Member.objects.get(user__email="sam@example.org")
        self.assertTrue(member.accepted_documents)
        self.assertIsNotNone(member.accepted_at)

    def test_signing_up_while_already_signed_in_just_goes_to_the_account(self):
        self.post()
        self.assertRedirects(self.post(email="other@example.org"),
                             reverse("accounts:dashboard"))
        self.assertEqual(UserModel.objects.count(), 1)

    def test_an_address_cannot_be_used_twice(self):
        self.post()
        self.client.logout()
        response = self.post(display_name="Someone Else")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already an account")
        self.assertEqual(UserModel.objects.filter(email__iexact="sam@example.org").count(), 1)

    def test_a_different_case_of_the_same_address_is_still_the_same_address(self):
        self.post()
        self.client.logout()
        response = self.post(email="SAM@EXAMPLE.ORG")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UserModel.objects.count(), 1)

    def test_a_welcome_email_goes_out(self):
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("sam@example.org", mail.outbox[0].to)
        self.assertIn("/account/verify/", mail.outbox[0].body)

    def test_a_new_account_starts_unverified(self):
        self.post()
        self.assertFalse(Member.objects.get(user__email="sam@example.org").is_verified)


@override_settings(**TEST_SETTINGS)
class VerificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = UserModel.objects.create_user(
            username="sam@example.org", email="sam@example.org", password="correct-horse-battery")
        self.member = Member.objects.create(user=self.user, display_name="Sam Park")

    def test_a_good_link_confirms_the_address(self):
        response = self.client.get(reverse("accounts:verify", args=[make_token(self.user)]))
        self.assertEqual(response.status_code, 200)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_verified)

    def test_using_the_link_twice_is_not_an_error(self):
        token = make_token(self.user)
        self.client.get(reverse("accounts:verify", args=[token]))
        self.member.refresh_from_db()
        first = self.member.email_verified_at

        self.client.get(reverse("accounts:verify", args=[token]))
        self.member.refresh_from_db()
        self.assertEqual(self.member.email_verified_at, first)

    def test_a_tampered_link_is_refused(self):
        response = self.client.get(reverse("accounts:verify", args=["not-a-real-token"]))
        self.assertEqual(response.status_code, 400)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_verified)

    def test_a_link_older_than_the_window_is_refused(self):
        from .emails import read_token

        token = signing.dumps({"uid": self.user.pk, "email": self.user.email}, salt=SALT)
        self.assertIsNotNone(read_token(token), "a fresh link should still work")
        self.assertIsNone(read_token(token, max_age=-1), "an aged-out link should not")

    def test_a_link_issued_for_an_old_address_does_not_verify_a_new_one(self):
        token = make_token(self.user)
        self.user.email = "someone.else@example.org"
        self.user.save(update_fields=["email"])

        response = self.client.get(reverse("accounts:verify", args=[token]))
        self.assertEqual(response.status_code, 400)
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_verified)


@override_settings(**TEST_SETTINGS)
class SignInTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = UserModel.objects.create_user(
            username="sam@example.org", email="sam@example.org", password="correct-horse-battery")
        Member.objects.create(user=self.user, display_name="Sam Park")

    def test_signing_in_with_the_email_address(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "sam@example.org", "password": "correct-horse-battery"})
        self.assertRedirects(response, reverse("accounts:dashboard"))

    def test_the_address_is_matched_whatever_the_case(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "SAM@Example.ORG", "password": "correct-horse-battery"})
        self.assertRedirects(response, reverse("accounts:dashboard"))

    def test_a_wrong_password_does_not_sign_anyone_in(self):
        response = self.client.post(reverse("accounts:login"), {
            "username": "sam@example.org", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_the_dashboard_needs_signing_in(self):
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)


@override_settings(**TEST_SETTINGS)
class DashboardTests(TestCase):
    def setUp(self):
        cache.clear()
        InterestArea.objects.create(name="Programming", order=0)
        self.user = UserModel.objects.create_user(
            username="sam@example.org", email="sam@example.org", password="correct-horse-battery")
        self.member = Member.objects.create(user=self.user, display_name="Sam Park")
        self.client.force_login(self.user)

    def test_a_member_can_change_their_own_details(self):
        response = self.client.post(reverse("accounts:dashboard"), {
            "display_name": "Sam P", "student": "no", "student_id": "",
            "interests": ["Programming"], "bio": "Hello.",
            "github_url": "", "linkedin_url": ""})
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.member.refresh_from_db()
        self.assertEqual(self.member.display_name, "Sam P")
        self.assertEqual(self.member.interests, ["Programming"])

    def test_a_member_cannot_set_their_own_membership_status(self):
        self.client.post(reverse("accounts:dashboard"), {
            "display_name": "Sam P", "student": "no", "student_id": "",
            "bio": "", "github_url": "", "linkedin_url": "",
            "status": Member.Status.ACTIVE})
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, Member.Status.PENDING)

    def test_the_dashboard_shows_applications_sent_from_the_same_address(self):
        Application.objects.create(name="Sam Park", email="SAM@example.org",
                                   message="Hello", created_at=timezone.now())
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Membership application")

    def test_one_member_cannot_see_another_members_application(self):
        Application.objects.create(name="Someone Else", email="other@example.org",
                                   message="Not yours", created_at=timezone.now())
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertNotContains(response, "Not yours")

    def test_asking_for_another_confirmation_email(self):
        mail.outbox = []
        response = self.client.post(reverse("accounts:resend_verification"))
        self.assertRedirects(response, reverse("accounts:dashboard"))
        self.assertEqual(len(mail.outbox), 1)

    def test_a_confirmed_member_is_not_sent_another_link(self):
        self.member.mark_verified()
        mail.outbox = []
        self.client.post(reverse("accounts:resend_verification"))
        self.assertEqual(len(mail.outbox), 0)
