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

@override_settings(**TEST_SETTINGS)
class AcceptCreatesAccountTests(TestCase):
    """Joining is the only door. There is no public sign-up; the leadership team
    creates the account when it accepts an application, and the person sets a
    password from the link that acceptance emails them."""

    def setUp(self):
        cache.clear()
        mail.outbox = []

    def _application(self, **overrides):
        data = dict(
            intent=Application.Intent.JOIN, name="Sam Park", email="sam@example.org",
            student="yes", student_id="20260001", interests=["Programming"],
            accepted_documents=True, accepted_at=timezone.now(),
            status=Application.Status.ACCEPTED,
        )
        data.update(overrides)
        return Application.objects.create(**data)

    def test_there_is_no_public_sign_up_route(self):
        from django.urls import NoReverseMatch

        with self.assertRaises(NoReverseMatch):
            reverse("accounts:signup")

    def test_accepting_creates_an_active_confirmed_member(self):
        from .services import accept_applications

        with self.captureOnCommitCallbacks(execute=True):
            created, approved = accept_applications([self._application()])
        self.assertEqual((created, approved), (1, 0))

        user = UserModel.objects.get(email="sam@example.org")
        self.assertEqual(user.username, "sam@example.org")
        member = user.member
        self.assertEqual(member.display_name, "Sam Park")
        self.assertEqual(member.student, "yes")
        self.assertEqual(member.student_id, "20260001")
        self.assertEqual(member.interests, ["Programming"])
        self.assertEqual(member.status, Member.Status.ACTIVE)
        self.assertTrue(member.is_verified)
        self.assertTrue(member.accepted_documents)
        self.assertIsNotNone(member.accepted_at)

    def test_the_new_account_has_no_usable_password_until_the_link_is_used(self):
        from .services import accept_applications

        with self.captureOnCommitCallbacks(execute=True):
            accept_applications([self._application()])
        self.assertFalse(UserModel.objects.get(email="sam@example.org").has_usable_password())

    def test_an_invite_email_with_a_set_password_link_goes_out(self):
        from .services import accept_applications

        with self.captureOnCommitCallbacks(execute=True):
            accept_applications([self._application()])
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn("sam@example.org", message.to)
        self.assertIn("Set your password", message.subject)
        self.assertIn("/account/password/reset/", message.body)

    def test_the_set_password_link_lets_them_choose_a_password(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from .services import accept_applications

        with self.captureOnCommitCallbacks(execute=True):
            accept_applications([self._application()])
        user = UserModel.objects.get(email="sam@example.org")
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Django's confirm view moves the token into the session and redirects
        # to a set-password form served under the literal "set-password" token.
        self.client.get(reverse("accounts:password_reset_confirm",
                                kwargs={"uidb64": uidb64, "token": token}))
        set_url = reverse("accounts:password_reset_confirm",
                          kwargs={"uidb64": uidb64, "token": "set-password"})
        response = self.client.post(set_url, {
            "new_password1": "correct-horse-battery",
            "new_password2": "correct-horse-battery"})
        self.assertEqual(response.status_code, 302)

        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(user.check_password("correct-horse-battery"))

    def test_a_question_does_not_create_an_account(self):
        from .services import accept_applications

        app = self._application(intent=Application.Intent.QUESTION, email="asker@example.org")
        with self.captureOnCommitCallbacks(execute=True):
            created, approved = accept_applications([app])
        self.assertEqual((created, approved), (0, 0))
        self.assertFalse(UserModel.objects.filter(email="asker@example.org").exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_accepting_the_same_person_twice_makes_only_one_account(self):
        from .services import accept_applications

        app = self._application()
        with self.captureOnCommitCallbacks(execute=True):
            accept_applications([app])
        with self.captureOnCommitCallbacks(execute=True):
            created, approved = accept_applications([app])
        self.assertEqual((created, approved), (0, 0))
        self.assertEqual(UserModel.objects.filter(email__iexact="sam@example.org").count(), 1)

    def test_an_existing_confirmed_account_is_approved_not_duplicated(self):
        from .services import accept_applications

        user = UserModel.objects.create_user(
            username="sam@example.org", email="sam@example.org", password="x")
        member = Member.objects.create(
            user=user, display_name="Sam", status=Member.Status.PENDING)
        member.mark_verified()

        with self.captureOnCommitCallbacks(execute=True):
            created, approved = accept_applications([self._application()])
        self.assertEqual((created, approved), (0, 1))
        member.refresh_from_db()
        self.assertEqual(member.status, Member.Status.ACTIVE)
        self.assertEqual(UserModel.objects.filter(email__iexact="sam@example.org").count(), 1)


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

    def profile_data(self, **overrides):
        data = {
            "display_name": "Sam P", "handle": self.member.handle,
            "profile_visibility": Member.Visibility.HIDDEN,
            "student": "no", "student_id": "", "interests": ["Programming"], "bio": "Hello.",
            "github_url": "", "linkedin_url": "",
            "projects-TOTAL_FORMS": "0", "projects-INITIAL_FORMS": "0",
            "projects-MIN_NUM_FORMS": "0", "projects-MAX_NUM_FORMS": "8",
        }
        data.update(overrides)
        return data

    def test_a_member_can_change_their_own_details(self):
        response = self.client.post(reverse("accounts:profile_edit"), self.profile_data())
        self.assertRedirects(response, reverse("accounts:profile_edit"))
        self.member.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.member.display_name, "Sam P")
        self.assertEqual(self.member.interests, ["Programming"])
        self.assertEqual(self.user.first_name, "Sam P", "the admin's copy of the name follows")

    def test_a_member_cannot_set_their_own_membership_status(self):
        self.client.post(reverse("accounts:profile_edit"),
                         self.profile_data(status=Member.Status.ACTIVE,
                                           approved_at="2026-01-01 00:00"))
        self.member.refresh_from_db()
        self.assertEqual(self.member.status, Member.Status.PENDING)
        self.assertIsNone(self.member.approved_at)

    def test_the_dashboard_does_not_accept_posts(self):
        self.assertEqual(self.client.post(reverse("accounts:dashboard")).status_code, 405)

    def test_the_dashboard_shows_applications_sent_from_the_same_address(self):
        # Only once the address is confirmed; see ApplicationPrivacyTests.
        self.member.mark_verified()
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
