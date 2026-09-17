"""An .ics calendar file for one event, so "add to calendar" works everywhere.

Written by hand against RFC 5545 rather than pulling in a library for forty
lines. The details that matter, and that are easy to get wrong:

  * Times are written in UTC with a trailing Z, so a member in another time
    zone gets the right local time in their own calendar.
  * Commas, semicolons, backslashes and newlines in text must be escaped, or
    a title like "Talks, pizza; demos" silently corrupts the file.
  * Lines longer than 75 octets are folded — octets, not characters, and a
    fold must never split a multi-byte character, which matters for Korean
    titles and names.
  * Lines end in CRLF.
  * The UID stays the same for the life of the event, and SEQUENCE goes up
    when the event changes, so a calendar updates the entry instead of adding
    a duplicate.
"""

from datetime import UTC
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone


def _escape(text):
    return (
        (text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
    )


def _fold(line):
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line
    pieces = []
    current = b""
    limit = 75
    for char in line:
        chunk = char.encode("utf-8")
        if len(current) + len(chunk) > limit:
            pieces.append(current.decode("utf-8"))
            current = b""
            limit = 74  # continuation lines start with a space, which counts
        current += chunk
    pieces.append(current.decode("utf-8"))
    return "\r\n ".join(pieces)


def _utc(value):
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def calendar_for(event, include_online_link=False):
    host = urlsplit(settings.APP_URL).hostname or "localhost"
    url = f"{settings.APP_URL}{event.get_absolute_url()}"

    description = [event.summary]
    if include_online_link and event.online_url:
        description.append(f"Join online: {event.online_url}")
    description.append(url)

    if event.location:
        location = event.location
    elif event.online_url:
        location = event.online_url if include_online_link else "Online"
    else:
        location = ""

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{_escape(settings.TEAM_NAME)}//Events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:event-{event.pk}@{host}",
        f"DTSTAMP:{_utc(timezone.now())}",
        f"DTSTART:{_utc(event.starts_at)}",
        f"DTEND:{_utc(event.ends_at)}",
        # Seconds since the event was created: it only ever goes up when the
        # event is edited, and stays small, unlike a raw Unix timestamp.
        f"SEQUENCE:{max(int((event.updated_at - event.created_at).total_seconds()), 0)}",
        f"SUMMARY:{_escape(event.title)}",
        f"DESCRIPTION:{_escape(chr(10).join(description))}",
        f"URL:{url}",
        f"STATUS:{'CANCELLED' if event.is_cancelled else 'CONFIRMED'}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    lines += ["END:VEVENT", "END:VCALENDAR"]

    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
