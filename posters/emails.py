"""Telling the team a presenter has sent their details and the poster is ready to check."""

import logging

from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from content.emails import build_message, html_layout, send_each

from .models import TalkPoster

log = logging.getLogger(__name__)


def send_submitted(talk_id):
    talk = TalkPoster.objects.filter(pk=talk_id).first()
    if talk is None or not settings.TEAM_INBOX:
        return
    review = f"{settings.APP_URL}{reverse('admin:posters_talkposter_change', args=[talk.pk])}"
    start = timezone.localtime(talk.starts_at)
    when = f"{start:%A} {start.day} {start:%B}, {start:%H:%M}"
    paragraphs = [
        f"{talk.speaker_name} has sent the details for “{talk.title}” ({when}), and the "
        f"poster is attached.",
        "It is not on the site yet. Check it, then attach it to an event or make a new event "
        "from it.",
    ]
    text = "\n\n".join(paragraphs + [f"Review it: {review}"])
    html = html_layout("A talk poster is ready to check", paragraphs, button=("Review it", review))
    with talk.poster.open("rb") as poster:
        attachment = (f"poster-{talk.pk}.png", poster.read(), "image/png")
    message = build_message(settings.TEAM_INBOX, f"[KDU Dev] Poster to check — {talk.title}",
                            text, html, attachments=[attachment])
    send_each([message], "a talk poster to check")
