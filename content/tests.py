from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Activity, FaqEntry, Page, SiteSettings, SocialLink


@override_settings(SECURE_SSL_REDIRECT=False)
class SeededSiteTests(TestCase):
    """Every page must render from the database, not from hard-coded copy."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_content", "--quiet")

    def test_seed_is_idempotent(self):
        before = (Activity.objects.count(), Page.objects.count(), FaqEntry.objects.count())
        call_command("seed_content", "--quiet")
        after = (Activity.objects.count(), Page.objects.count(), FaqEntry.objects.count())
        self.assertEqual(before, after, "re-seeding must not duplicate rows")

    def test_every_top_level_page_renders(self):
        for name in ["content:home", "content:about", "content:activities", "content:join",
                     "content:faq", "content:interests", "content:resources", "content:contents"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "site-footer")

    def test_every_activity_has_a_page(self):
        self.assertEqual(Activity.objects.count(), 7)
        for activity in Activity.objects.all():
            with self.subTest(activity=activity.slug):
                response = self.client.get(activity.get_absolute_url())
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, activity.name)
                self.assertContains(response, activity.cadence)

    def test_every_prose_page_renders_with_its_sections(self):
        for page in Page.objects.all():
            with self.subTest(page=page.slug):
                response = self.client.get(page.get_absolute_url())
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, page.title)
                for section in page.sections.all():
                    self.assertContains(response, section.heading)

    def test_unknown_slug_is_a_404(self):
        self.assertEqual(self.client.get("/no-such-page/").status_code, 404)

    def test_unpublished_content_disappears_from_the_site(self):
        activity = Activity.objects.first()
        url = activity.get_absolute_url()
        self.assertEqual(self.client.get(url).status_code, 200)

        activity.published = False
        activity.save()

        self.assertEqual(self.client.get(url).status_code, 404, "hidden means hidden")
        listing = self.client.get(reverse("content:activities"))
        self.assertNotContains(listing, activity.name)

    def test_editing_content_changes_the_page(self):
        page = Page.objects.get(slug="rules")
        section = page.sections.first()
        section.heading = "A heading edited in the admin"
        section.save()
        response = self.client.get(page.get_absolute_url())
        self.assertContains(response, "A heading edited in the admin")

    def test_a_link_with_no_address_shows_soon_rather_than_a_dead_link(self):
        SocialLink.objects.create(name="Discord", group=SocialLink.GROUP_CHAT, url="")
        response = self.client.get(reverse("content:home"))
        self.assertContains(response, "Soon")
        self.assertNotContains(response, 'href=""')

    def test_filling_in_an_address_makes_it_a_link_everywhere(self):
        link = SocialLink.objects.create(name="Discord", group=SocialLink.GROUP_CHAT, url="")
        link.url = "https://discord.gg/example"
        link.save()

        for page in ("content:home", "content:about", "content:join"):
            with self.subTest(page=page):
                self.assertContains(self.client.get(reverse(page)), "https://discord.gg/example")

    def test_the_two_link_groups_are_listed_under_their_own_headings(self):
        SocialLink.objects.create(name="WhatsApp", group=SocialLink.GROUP_CHAT,
                                  url="https://example.org/w")
        SocialLink.objects.create(name="LinkedIn", group=SocialLink.GROUP_SOCIAL,
                                  url="https://example.org/l")
        response = self.client.get(reverse("content:home"))
        self.assertContains(response, "Where we talk")
        self.assertContains(response, "Follow us")

    def test_an_unpublished_link_is_not_shown(self):
        SocialLink.objects.create(name="Facebook", group=SocialLink.GROUP_SOCIAL,
                                  url="https://example.org/fb", published=False)
        self.assertNotContains(self.client.get(reverse("content:home")), "https://example.org/fb")

    def test_site_settings_is_a_singleton(self):
        SiteSettings.objects.create(community_name="Another one")
        self.assertEqual(SiteSettings.objects.count(), 1)

    def test_join_form_offers_the_interest_areas_from_the_database(self):
        response = self.client.get(reverse("content:join"))
        self.assertContains(response, 'name="interests"')
        self.assertContains(response, "Programming")
        self.assertContains(response, 'name="agree"')
        self.assertContains(response, 'name="consent"')

    def test_pages_carry_their_own_title_and_description(self):
        response = self.client.get(reverse("content:about"))
        self.assertContains(response, "<title>About")
        self.assertContains(response, 'name="description"')
