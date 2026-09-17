"""Small pieces other pages use to mention events, without knowing how they work."""

from django import template
from django.utils import timezone

from ..models import Event

register = template.Library()


@register.simple_tag(takes_context=True)
def next_event(context):
    """The next event this viewer is allowed to see, or None."""
    request = context.get("request")
    user = getattr(request, "user", None)
    return (Event.objects.visible_to(user)
            .filter(status=Event.Status.PUBLISHED)
            .upcoming(timezone.now())
            .order_by("starts_at", "pk")
            .first())


@register.simple_tag(takes_context=True)
def upcoming_events_for(context, activity, limit=3):
    request = context.get("request")
    user = getattr(request, "user", None)
    return list(Event.objects.visible_to(user)
                .filter(activity=activity, status=Event.Status.PUBLISHED)
                .upcoming(timezone.now())
                .order_by("starts_at", "pk")[:limit])
