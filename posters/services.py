"""What happens to a talk poster: storing the photo, drawing the poster, approving it."""

import io
import uuid

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps

from content.models import SiteSettings
from events.models import Event

from .models import Platform, TalkPoster
from .render import PosterContent, render

ICONS = {Platform.DISCORD: "discord", Platform.IN_PERSON: "pin"}

# Big enough for the poster's photo frame at twice its printed size; anything
# larger only costs disk space.
PHOTO_LONGEST_SIDE = 2000


def store_photo(talk, upload):
    """Keep a clean copy of the presenter's photo.

    Phones save the way up in the EXIF data rather than in the pixels, so the
    picture is turned upright first. It is then saved again as a JPEG with no
    EXIF at all: a phone photo's EXIF can carry the place it was taken, and the
    presenter did not mean to send that.
    """
    upload.seek(0)
    with Image.open(upload) as original:
        picture = ImageOps.exif_transpose(original).convert("RGB")
    picture.thumbnail((PHOTO_LONGEST_SIDE, PHOTO_LONGEST_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    picture.save(out, "JPEG", quality=90, optimize=True)
    _replace(talk, "photo", f"{uuid.uuid4().hex}.jpg", out.getvalue())


def draw(talk):
    """Draw the poster from what the talk holds now, replacing any earlier one."""
    place, place_detail = talk.place_lines()
    content = PosterContent(
        label=talk.label, title=talk.title, summary=talk.summary,
        speaker_name=talk.speaker_name, speaker_tag=talk.speaker_tag, about=talk.about,
        starts_at=talk.starts_at, ends_at=talk.ends_at,
        place=place, place_detail=place_detail, icon=ICONS.get(talk.platform, "video"),
        link=SiteSettings.get().poster_link,
    )
    with talk.photo.open("rb") as stored, Image.open(stored) as photo:
        png = render(content, photo.convert("RGB"))
    _replace(talk, "poster", f"{talk.pk}-{uuid.uuid4().hex[:12]}.png", png)


def _replace(talk, field_name, filename, data):
    field = getattr(talk, field_name)
    old = field.name
    field.save(filename, ContentFile(data), save=False)
    if old and old != field.name:
        # After the row is saved, so a failed save does not leave it pointing
        # at a file that has gone.
        storage = field.storage
        transaction.on_commit(lambda: storage.delete(old))


def approve(talk, user, event):
    talk.event = event
    talk.status = TalkPoster.Status.APPROVED
    talk.approved_at = timezone.now()
    talk.approved_by = user
    talk.save()


def create_event(talk, user, status, online_url=""):
    """A new event made from the talk: its title, summary, presenter, time and place."""
    event = Event(
        title=talk.title,
        summary=talk.summary,
        description=talk.about,
        presenter=talk.speaker_name,
        starts_at=talk.starts_at,
        ends_at=talk.ends_at,
        # An online event still says where: "Online, on Zoom".
        location=(f"Online, on {talk.get_platform_display()}" if talk.is_online
                  else ", ".join(p for p in talk.place_lines() if p)),
        online_url=online_url,
        status=status,
        created_by=user,
    )
    event.full_clean()
    event.save()
    return event
