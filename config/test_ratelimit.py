"""The rate limiter reads the address nginx saw, not the one a client claims."""

from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from .ratelimit import client_ip, rate_limited

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@override_settings(CACHES=LOCMEM, RATE_LIMIT_MAX=3, RATE_LIMIT_WINDOW_SECONDS=600)
class RateLimitTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()

    def request(self, **meta):
        return self.factory.post("/", **meta)

    def test_x_real_ip_wins_when_nginx_sets_it(self):
        request = self.request(HTTP_X_REAL_IP="198.51.100.7",
                               HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7",
                               REMOTE_ADDR="10.0.0.1")
        self.assertEqual(client_ip(request), "198.51.100.7")

    def test_without_x_real_ip_the_last_forwarded_hop_is_trusted_not_the_first(self):
        request = self.request(HTTP_X_FORWARDED_FOR="1.2.3.4, 198.51.100.7")
        self.assertEqual(client_ip(request), "198.51.100.7")

    def test_a_made_up_forwarded_header_does_not_buy_a_fresh_allowance(self):
        # The old limiter read the first entry, which the client writes, so a
        # new fake address on every request was never limited.
        for n in range(3):
            request = self.request(HTTP_X_FORWARDED_FOR=f"203.0.113.{n}, 198.51.100.7")
            self.assertFalse(rate_limited(request, scope="signup"))
        spoofed = self.request(HTTP_X_FORWARDED_FOR="203.0.113.99, 198.51.100.7")
        self.assertTrue(rate_limited(spoofed, scope="signup"))

    def test_scopes_do_not_share_an_allowance(self):
        request = self.request(REMOTE_ADDR="192.0.2.10")
        for _ in range(3):
            rate_limited(request, scope="signup")
        self.assertTrue(rate_limited(request, scope="signup"))
        self.assertFalse(rate_limited(request, scope="form"))

    def test_a_higher_limit_can_be_asked_for(self):
        request = self.request(REMOTE_ADDR="192.0.2.20")
        for _ in range(10):
            self.assertFalse(rate_limited(request, scope="events", limit=30))
