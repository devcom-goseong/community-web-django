"""Handles, and the rules for links members put on their own profiles.

A handle is the readable part of a profile address, /members/sam-park/, so it
is what a member puts on a CV. It is ASCII only on purpose: slugify() drops
Hangul entirely, so a name like 김민수 produces an empty slug, and URL routing
only matches ASCII slugs. Rather than fail, those accounts get a neutral
generated handle that the member can change.

Links are restricted to http and https, and the GitHub and LinkedIn fields to
those sites. Otherwise a profile on the community's own domain becomes a free
place to host a link to anything, which is exactly what a spammer looks for.
"""

import re
import secrets
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.utils.text import slugify

HANDLE_MIN, HANDLE_MAX = 3, 30
HANDLE_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")

# Words that would read as the site speaking, or that could collide with a
# route under /members/ now or later.
RESERVED_HANDLES = frozenset({
    "about", "account", "accounts", "admin", "administrator", "api", "edit", "events",
    "help", "join", "kdu", "leader", "leaders", "leadership", "login", "logout", "me",
    "member", "members", "moderator", "new", "official", "profile", "profiles", "root",
    "search", "settings", "sign-in", "sign-out", "sign-up", "signin", "signout", "signup",
    "staff", "static", "support", "system", "team", "www",
})


def validate_handle(value):
    if not HANDLE_MIN <= len(value) <= HANDLE_MAX:
        raise ValidationError(
            f"Use between {HANDLE_MIN} and {HANDLE_MAX} characters.", code="length")
    if not HANDLE_PATTERN.match(value) or "--" in value:
        raise ValidationError(
            "Use lowercase letters, numbers and single hyphens, starting and ending with a "
            "letter or number.", code="invalid")
    if value in RESERVED_HANDLES:
        raise ValidationError("That one is reserved. Please choose another.", code="reserved")


def handle_base(display_name):
    """The readable starting point for a handle, or '' if the name has none."""
    base = slugify(display_name or "")[:HANDLE_MAX - 7].strip("-")
    base = re.sub(r"-{2,}", "-", base)
    if len(base) < HANDLE_MIN or base in RESERVED_HANDLES:
        return ""
    return base


def generate_handle(display_name, is_taken):
    """A valid, unused handle. `is_taken(candidate)` answers the uniqueness question."""
    base = handle_base(display_name)
    if base and not is_taken(base):
        return base
    stem = base or "member"
    for _ in range(20):
        candidate = f"{stem}-{secrets.token_hex(3)}"
        if not is_taken(candidate):
            return candidate
    # Twenty collisions on 24 bits of randomness does not happen; if it somehow
    # does, fail loudly rather than loop forever.
    raise RuntimeError("could not find a free handle")


def validate_web_url(value):
    if not value:
        return
    scheme = urlsplit(value).scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValidationError("Use a link that starts with https:// or http://.", code="scheme")


def _host(value):
    return (urlsplit(value).hostname or "").lower().rstrip(".")


def validate_github_url(value):
    if not value:
        return
    validate_web_url(value)
    if _host(value) not in {"github.com", "www.github.com"}:
        raise ValidationError(
            "This should be a github.com address, for example https://github.com/your-name.",
            code="host")


def validate_linkedin_url(value):
    if not value:
        return
    validate_web_url(value)
    host = _host(value)
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        raise ValidationError(
            "This should be a linkedin.com address, for example "
            "https://www.linkedin.com/in/your-name.", code="host")
