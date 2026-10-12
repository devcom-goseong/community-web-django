"""The password pages stop answering once they are being guessed at.

What matters in here, in order: a wrong password many times over stops being
answered; the right password is never held against anyone; nothing but getting
the password right clears the count; and the three counters do not interfere
with each other.

The other test modules deal with the https redirect by switching
SECURE_SSL_REDIRECT off, since with DEBUG off an http:// request from the test
client is answered with a 301 and never reaches a view. This one instead posts
everything with secure=True and leaves the redirect alone, because the
redirect is the subject: an earlier version of the middleware decided a
password had been right by seeing a redirect come back, and that 301 was
enough to clear the count. Turning the thing off would hide the bug these
tests exist to keep out. One test below posts over http deliberately.
"""

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.factories import PASSWORD, make_member, make_staff

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Small enough to reach in a test and still prove the three limits differ.
LIMITS = dict(
    CACHES=LOCMEM,
    LOGIN_FAIL_MAX=3,
    LOGIN_FAIL_ACCOUNT_MAX=5,
    LOGIN_FAIL_SHARED_MAX=6,
    LOGIN_FAIL_WINDOW_SECONDS=900,
    VAULT_PASSWORD="the-real-vault-password",
)


@override_settings(**LIMITS)
class SignInThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.member = make_member()
        self.url = reverse("accounts:login")

    def wrong(self, email=None, ip="198.51.100.5", **extra):
        return self.client.post(self.url, {
            "username": email or self.member.email,
            "password": "not-the-password",
        }, secure=True, HTTP_X_REAL_IP=ip, **extra)

    def right(self, ip="198.51.100.5"):
        return self.client.post(self.url, {
            "username": self.member.email,
            "password": PASSWORD,
        }, secure=True, HTTP_X_REAL_IP=ip)

    def test_a_wrong_password_over_and_over_stops_being_answered(self):
        for _ in range(3):
            self.assertEqual(self.wrong().status_code, 200)
        refused = self.wrong()
        self.assertEqual(refused.status_code, 429)
        self.assertEqual(refused["Retry-After"], "900")

    def test_the_refusal_says_how_long_and_offers_the_reset_link(self):
        for _ in range(4):
            self.wrong()
        page = self.wrong().content.decode()
        self.assertIn("15 minutes", page)
        self.assertIn(reverse("accounts:password_reset"), page)

    def test_the_right_password_is_never_held_against_anyone(self):
        # Counting requests rather than failures would lock out a member who
        # signs in on a phone and a laptop and then a borrowed machine.
        for _ in range(10):
            self.assertEqual(self.right().status_code, 302)
            self.client.logout()

    def test_getting_in_clears_what_went_before(self):
        self.wrong()
        self.wrong()
        self.assertEqual(self.right().status_code, 302)
        self.client.logout()
        # The two earlier failures are forgotten, so these two do not reach
        # the limit of three and the form is still answered.
        self.wrong()
        self.assertEqual(self.wrong().status_code, 200)

    @override_settings(SECURE_SSL_REDIRECT=True)
    def test_nothing_but_the_password_clears_the_count(self):
        # The middleware used to decide a password had been right by looking
        # for a redirect in the answer. Django redirects an insecure request
        # to https before the view runs, so this request alone was enough to
        # wipe the count and walk around the limit for ever.
        for _ in range(3):
            self.wrong()
        bounced = self.client.post(self.url, {
            "username": self.member.email, "password": "not-the-password",
        }, secure=False, HTTP_X_REAL_IP="198.51.100.5")
        self.assertEqual(bounced.status_code, 301)
        self.assertEqual(self.wrong().status_code, 429)

    def test_one_account_cannot_be_worked_on_from_many_addresses(self):
        # Every address stays under the per-connection limit, so only the
        # per-account counter can notice this.
        for n in range(5):
            self.assertEqual(self.wrong(ip=f"203.0.113.{n}").status_code, 200)
        self.assertEqual(self.wrong(ip="203.0.113.200").status_code, 429)

    def test_a_locked_account_does_not_lock_everybody(self):
        other = make_member()
        for n in range(5):
            self.wrong(ip=f"203.0.113.{n}")
        self.assertEqual(self.wrong(ip="203.0.113.200").status_code, 429)
        reply = self.client.post(self.url, {
            "username": other.email, "password": PASSWORD,
        }, secure=True, HTTP_X_REAL_IP="203.0.113.201")
        self.assertEqual(reply.status_code, 302)

    def test_a_made_up_forwarded_header_does_not_buy_more_tries(self):
        for n in range(3):
            self.client.post(self.url, {
                "username": self.member.email, "password": "no",
            }, secure=True, HTTP_X_FORWARDED_FOR=f"203.0.113.{n}, 198.51.100.9")
        spoofed = self.client.post(self.url, {
            "username": self.member.email, "password": "no",
        }, secure=True, HTTP_X_FORWARDED_FOR="203.0.113.99, 198.51.100.9")
        self.assertEqual(spoofed.status_code, 429)

    def test_a_get_is_not_counted_and_other_pages_are_untouched(self):
        for _ in range(6):
            self.assertEqual(self.client.get(self.url, secure=True).status_code, 200)
        self.assertEqual(self.wrong().status_code, 200)


@override_settings(**LIMITS)
class AdminSignInThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.staff = make_staff()
        self.url = reverse("admin:login")

    def guess(self, password="not-it", ip="198.51.100.21"):
        return self.client.post(self.url, {
            "username": self.staff.username, "password": password,
        }, secure=True, HTTP_X_REAL_IP=ip)

    def test_the_admin_sign_in_is_covered_as_well(self):
        # It is Django's own view, which is why the counting listens to
        # Django's own signals instead of being written into ours.
        for _ in range(3):
            self.assertEqual(self.guess().status_code, 200)
        self.assertEqual(self.guess().status_code, 429)

    def test_getting_into_the_admin_clears_its_count(self):
        self.guess()
        self.guess()
        self.assertEqual(self.guess(password=PASSWORD).status_code, 302)
        self.client.logout()
        self.guess()
        self.assertEqual(self.guess().status_code, 200)

    def test_the_admin_counter_is_not_the_members_counter(self):
        for _ in range(4):
            self.guess(ip="198.51.100.22")
        member = make_member()
        reply = self.client.post(reverse("accounts:login"), {
            "username": member.email, "password": PASSWORD,
        }, secure=True, HTTP_X_REAL_IP="198.51.100.22")
        self.assertEqual(reply.status_code, 302)


@override_settings(**LIMITS)
class VaultThrottleTests(TestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("vault:unlock")

    def guess(self, ip="198.51.100.31", password="wrong"):
        return self.client.post(
            self.url, {"password": password}, secure=True, HTTP_X_REAL_IP=ip)

    def test_one_address_is_cut_off_after_a_few_guesses(self):
        for _ in range(3):
            self.assertEqual(self.guess().status_code, 200)
        self.assertEqual(self.guess().status_code, 429)

    def test_every_failure_counts_together_however_many_places_they_come_from(self):
        # One shared password has no account to count against, so a thousand
        # hosts trying a handful each would otherwise never reach a limit.
        for n in range(6):
            self.assertEqual(self.guess(ip=f"192.0.2.{n}").status_code, 200)
        self.assertEqual(self.guess(ip="192.0.2.99").status_code, 429)

    def test_the_real_password_still_opens_it(self):
        reply = self.guess(password="the-real-vault-password")
        self.assertEqual(reply.status_code, 302)
        self.assertTrue(self.client.session.get("vault_ok"))

    def test_opening_it_clears_the_count(self):
        self.guess()
        self.guess()
        self.assertEqual(self.guess(password="the-real-vault-password").status_code, 302)
        self.client.session.flush()
        self.guess()
        self.assertEqual(self.guess().status_code, 200)

    def test_an_empty_password_setting_opens_nothing(self):
        with override_settings(VAULT_PASSWORD=""):
            reply = self.client.post(self.url, {"password": ""}, secure=True)
            self.assertEqual(reply.status_code, 200)
            self.assertFalse(self.client.session.get("vault_ok"))
