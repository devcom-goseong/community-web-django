"""Structured data (schema.org JSON-LD) for search engines.

Kept out of the templates on purpose: building JSON by hand in a template is how
invalid JSON ships — a missing comma, or an unescaped quote in a name, breaks
the whole block and a crawler silently discards it. Here it is one json.dumps,
escaped correctly, and the template only prints it.

Only public things are described. A members-only event's page carries no
structured data at all, and an event's online link — which the site is careful
never to show to anyone without a place — is never placed here either.
"""

import json

from django.templatetags.static import static
from django.utils.safestring import mark_safe

from events.models import Event


def _abs(request, path):
    return request.build_absolute_uri(path)


def _organization(request, site, same_as):
    home = _abs(request, "/")
    org = {
        "@type": "Organization",
        "@id": home + "#org",
        "name": site.community_name,
        "url": home,
        "logo": _abs(request, static("assets/images/logo-mark-large.png")),
        "location": {
            "@type": "Place",
            "name": site.university,
            "address": {"@type": "PostalAddress", "addressCountry": site.country},
        },
    }
    if same_as:
        org["sameAs"] = list(same_as)
    return org


def site_ld(request, site, same_as):
    """Organization + WebSite, rendered into every public page's head."""
    home = _abs(request, "/")
    website = {
        "@type": "WebSite",
        "@id": home + "#website",
        "name": site.community_name,
        "url": home,
        "inLanguage": "en",
        "publisher": {"@id": home + "#org"},
    }
    graph = {"@context": "https://schema.org",
             "@graph": [_organization(request, site, same_as), website]}
    return mark_safe(json.dumps(graph, ensure_ascii=False))


def event_ld(request, event):
    """schema.org/Event for a public, published event — otherwise nothing.

    The online link is deliberately left out: it is shown only to people who
    have a place, so it must never travel in markup a crawler reads.
    """
    if event.visibility != Event.Visibility.PUBLIC or event.status != Event.Status.PUBLISHED:
        return ""
    from .models import SiteSettings
    site = SiteSettings.get()
    home = _abs(request, "/")
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.title,
        "description": event.summary,
        "startDate": event.starts_at.isoformat(),
        "endDate": event.ends_at.isoformat(),
        "eventStatus": ("https://schema.org/EventCancelled" if event.is_cancelled
                        else "https://schema.org/EventScheduled"),
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": _abs(request, event.get_absolute_url()),
        "organizer": {"@type": "Organization", "name": site.community_name, "url": home},
        "location": {
            "@type": "Place",
            "name": event.location or site.university,
            "address": {"@type": "PostalAddress", "addressCountry": site.country},
        },
    }
    return mark_safe(json.dumps(data, ensure_ascii=False))
