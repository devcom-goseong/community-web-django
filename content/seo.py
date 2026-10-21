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
from django.utils import timezone
from django.utils.safestring import mark_safe

from events.models import Event

# Events carry no picture of their own, so they use the site's share image (wide) and the
# large logo (square): Google asks for an event image and prefers several aspect ratios.
EVENT_IMAGES = ("assets/images/og-image.png", "assets/images/logo-mark-large.png")

# Every event is free to attend; the community meets at Kyungdong University in Korea.
PRICE_CURRENCY = "KRW"


def _abs(request, path):
    return request.build_absolute_uri(path)


def _offer(request, event):
    """A free place at the event. Registering happens on the event's own page, so that is
    the offer's url. Places are 'sold out' once the event is full, registration has closed
    or the event has begun."""
    open_now = timezone.now() < event.registration_deadline
    spots = event.spots_left()
    available = open_now and not event.is_cancelled and (spots is None or spots > 0)
    return {
        "@type": "Offer",
        "price": "0",
        "priceCurrency": PRICE_CURRENCY,
        "availability": ("https://schema.org/InStock" if available
                         else "https://schema.org/SoldOut"),
        "url": _abs(request, event.get_absolute_url()),
        "validFrom": event.created_at.isoformat(),
    }


def _performer(event, organizer):
    """The presenter when the event names one, otherwise the community that runs it."""
    if event.presenter:
        return {"@type": "Person", "name": event.presenter}
    return organizer


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


def event_ld(request, event, poster_url=""):
    """schema.org/Event for a public, published event — otherwise nothing.

    The online link is deliberately left out: it is shown only to people who
    have a place, so it must never travel in markup a crawler reads. An
    approved talk poster, when there is one, is the event's first image.
    """
    if event.visibility != Event.Visibility.PUBLIC or event.status != Event.Status.PUBLISHED:
        return ""
    from .models import SiteSettings
    site = SiteSettings.get()
    home = _abs(request, "/")
    organizer = {"@type": "Organization", "name": site.community_name, "url": home}
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
        "image": ([_abs(request, poster_url)] if poster_url else [])
                 + [_abs(request, static(path)) for path in EVENT_IMAGES],
        "organizer": organizer,
        "performer": _performer(event, organizer),
        "offers": _offer(request, event),
        "location": {
            "@type": "Place",
            "name": event.location or site.university,
            "address": {"@type": "PostalAddress", "addressCountry": site.country},
        },
    }
    return mark_safe(json.dumps(data, ensure_ascii=False))
