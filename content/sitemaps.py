"""The XML sitemap: every public, indexable address in one place.

Only things anyone may see are listed. The account pages, the member directory
and members-only events are left out — they are disallowed in robots.txt and
carry noindex, and naming them here would work against both. URLs are https,
because that is the only scheme the site answers on.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from events.models import Event

from .models import Activity, Page


class StaticViewSitemap(Sitemap):
    protocol = "https"
    changefreq = "weekly"

    def items(self):
        return [
            "content:home", "content:about", "content:activities",
            "content:join", "content:faq", "content:interests", "content:resources",
            "events:list",
        ]

    def location(self, name):
        return reverse(name)

    def priority(self, name):
        return 1.0 if name == "content:home" else 0.7


class PageSitemap(Sitemap):
    protocol = "https"
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return Page.objects.live()

    def lastmod(self, page):
        return page.updated_at


class ActivitySitemap(Sitemap):
    protocol = "https"
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Activity.objects.live()

    def lastmod(self, activity):
        return activity.updated_at


class EventSitemap(Sitemap):
    protocol = "https"
    changefreq = "daily"
    priority = 0.6

    def items(self):
        return (Event.objects
                .filter(status=Event.Status.PUBLISHED, visibility=Event.Visibility.PUBLIC)
                .order_by("-starts_at"))

    def lastmod(self, event):
        return event.updated_at


SITEMAPS = {
    "static": StaticViewSitemap,
    "pages": PageSitemap,
    "activities": ActivitySitemap,
    "events": EventSitemap,
}
