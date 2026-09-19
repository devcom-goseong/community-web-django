"""The SEO surface: the sitemap, robots.txt, and the JSON-LD structured data.

The point of the leak tests is the same promise the rest of the site keeps: a
members-only event, and the online link that only attendees may see, must not
be handed to a search engine.
"""

from datetime import timedelta

from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from events.models import Event

TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "GOOGLE_SITE_VERIFICATION": "test-token-123",
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
}


def _make_event(**overrides):
    start = timezone.now() + timedelta(days=3)
    data = {
        "title": "Open Demo Day",
        "summary": "Come and see what people have built this term.",
        "starts_at": start,
        "ends_at": start + timedelta(hours=2),
        "visibility": Event.Visibility.PUBLIC,
        "status": Event.Status.PUBLISHED,
    }
    data.update(overrides)
    return Event.objects.create(**data)


@override_settings(**TEST_SETTINGS)
class SitemapTests(TestCase):
    def test_sitemap_is_served_and_lists_the_home_page(self):
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"<urlset", resp.content)
        self.assertIn(b"https://testserver/</loc>", resp.content)

    def test_sitemap_lists_a_public_event_but_not_a_members_only_one(self):
        public = _make_event(title="Public Talk")
        hidden = _make_event(title="Members Night", visibility=Event.Visibility.MEMBERS)
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(public.get_absolute_url(), body)
        self.assertNotIn(hidden.get_absolute_url(), body)

    def test_robots_points_at_the_sitemap_and_blocks_private_areas(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Sitemap: http://testserver/sitemap.xml", body)
        self.assertIn("Disallow: /members/", body)
        self.assertIn("Disallow: /account/", body)


@override_settings(**TEST_SETTINGS)
class StructuredDataTests(TestCase):
    def test_home_carries_organization_and_website_json_ld(self):
        resp = self.client.get("/")
        self.assertContains(resp, 'type="application/ld+json"')
        self.assertContains(resp, '"@type": "Organization"')
        self.assertContains(resp, '"@type": "WebSite"')

    def test_verification_meta_is_rendered_when_configured(self):
        resp = self.client.get("/")
        self.assertContains(
            resp, 'name="google-site-verification" content="test-token-123"')

    def test_a_public_event_page_carries_event_json_ld(self):
        event = _make_event()
        resp = self.client.get(event.get_absolute_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '"@type": "Event"')
        self.assertContains(resp, "Open Demo Day")

    def test_event_json_ld_is_empty_for_a_members_only_event(self):
        from content.seo import event_ld
        event = Event(
            title="Members Night", summary="For members.",
            starts_at=timezone.now(), ends_at=timezone.now() + timedelta(hours=1),
            visibility=Event.Visibility.MEMBERS, status=Event.Status.PUBLISHED)
        self.assertEqual(event_ld(RequestFactory().get("/"), event), "")

    def test_event_json_ld_never_carries_the_members_only_online_link(self):
        from content.seo import event_ld
        event = _make_event(online_url="https://meet.example.com/secret-room")
        rendered = event_ld(RequestFactory().get("/"), event)
        self.assertIn('"@type": "Event"', rendered)
        self.assertNotIn("meet.example.com", rendered)
