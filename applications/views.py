"""The form endpoint.

Deliberately answers with exactly the JSON shape the existing front end
already understands, so js/form.js on the public site needs no change beyond
pointing at this host:

    success  200 {"ok": true}
    invalid  422 {"ok": false, "message": "...", "fields": ["name", ...]}
    refused  400/429/502 {"ok": false, "message": "..."}

A form-encoded POST (the no-JavaScript path) gets a small HTML page instead,
matching the behaviour the site already documents.
"""

import hashlib
import json
import logging
import re
import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.utils.html import escape
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .emails import send_application_emails
from .models import Application

log = logging.getLogger(__name__)

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
LIMITS = {"name": 120, "email": 160, "student_id": 40, "message": 2000}
MAX_INTERESTS = 12


def _clean(value, limit):
    return str(value if value is not None else "").strip()[:limit]


def _header_safe(value, limit):
    """Strip CR/LF so nothing submitted can be smuggled into a mail header."""
    return re.sub(r"[\r\n]+", " ", str(value if value is not None else "")).strip()[:limit]


def _truthy(value):
    return value in (True, "yes", "on", "true", "1", 1)


def _client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _rate_limited(request, scope="form"):
    """Best-effort per-IP limit.

    The IP is hashed and only ever lives in the cache, never in the database,
    because the published privacy notice says it is not stored.

    `scope` keeps separate counters for separate things. Without it, somebody
    creating an account would spend the same budget as somebody sending the
    join form, and on a shared university connection the two would starve each
    other for reasons neither person could see.
    """
    ip = _client_ip(request)
    if not ip:
        return False
    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]
    key = f"ratelimit:{scope}:{digest}"
    try:
        hits = cache.get_or_set(key, 0, settings.RATE_LIMIT_WINDOW_SECONDS)
        hits = cache.incr(key)
    except ValueError:
        cache.set(key, 1, settings.RATE_LIMIT_WINDOW_SECONDS)
        hits = 1
    except Exception:  # a cache backend problem must not block a real applicant
        log.exception("rate limiter unavailable; allowing the request")
        return False
    return hits > settings.RATE_LIMIT_MAX


def _parse(request):
    """Return (data, wants_json). Understands JSON and form encoding."""
    content_type = (request.content_type or "").lower()
    if "application/json" in content_type:
        try:
            return json.loads(request.body.decode("utf-8") or "{}"), True
        except (ValueError, UnicodeDecodeError):
            return None, True
    data = {key: request.POST.getlist(key) if key == "interests" else request.POST.get(key)
            for key in request.POST.keys()}
    return data, False


def _html(status, heading, message):
    site = settings.PUBLIC_SITE_URL
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(heading)} &mdash; {escape(settings.TEAM_NAME)}</title>
<meta name="robots" content="noindex">
<link rel="stylesheet" href="{site}/css/variables.css">
<link rel="stylesheet" href="{site}/css/base.css">
<link rel="stylesheet" href="{site}/css/components.css">
</head>
<body>
<main id="main" class="section">
  <div class="wrap wrap--narrow">
    <p class="caption">{escape(settings.TEAM_NAME)}</p>
    <h1 class="page-head__title">{escape(heading)}</h1>
    <p class="page-head__lead">{escape(message)}</p>
    <p class="mt-8"><a class="btn" href="{site}/index.html">Back to the site</a></p>
  </div>
</main>
</body>
</html>"""
    return HttpResponse(body, status=status, content_type="text/html; charset=utf-8")


def _fail(wants_json, status, message, fields=None):
    if wants_json:
        return JsonResponse({"ok": False, "message": message, "fields": fields or []}, status=status)
    return _html(status, "That did not go through", message)


def _succeed(wants_json, email):
    if wants_json:
        return JsonResponse({"ok": True})
    return _html(
        200,
        "Thank you — we have it",
        f"A confirmation is on its way to {email}. Someone on the leadership team "
        f"will read what you wrote and reply to you directly.",
    )


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def register(request):
    if request.method == "OPTIONS":
        return HttpResponse(status=204)

    data, wants_json = _parse(request)
    if data is None:
        return _fail(wants_json, 400, "We could not read that submission. Please try again.")

    # Honeypot. Answer as though it worked so an automated submitter learns
    # nothing, and drop it.
    if _clean(data.get("website"), 200):
        log.info("register: honeypot triggered; submission dropped")
        return _succeed(wants_json, _clean(data.get("email"), LIMITS["email"]))

    # Timing. Only enforced when the browser supplied a timestamp, so the
    # no-JavaScript path still works.
    try:
        stamp = float(data.get("ts") or 0) / 1000.0
    except (TypeError, ValueError):
        stamp = 0
    if stamp > 0:
        elapsed = time.time() - stamp
        if elapsed < settings.MIN_FILL_SECONDS or elapsed > settings.MAX_FILL_SECONDS:
            return _fail(
                wants_json, 400,
                "That form was open for an unusual length of time. Please reload the page "
                "and send it again.",
            )

    if _rate_limited(request):
        return _fail(wants_json, 429,
                     "That is a lot of messages at once. Please try again in a few minutes.")

    intent = "question" if data.get("intent") == "question" else "join"
    raw_interests = data.get("interests") or []
    if isinstance(raw_interests, str):
        raw_interests = [raw_interests]

    application = Application(
        intent=intent,
        name=_header_safe(data.get("name"), LIMITS["name"]),
        email=_header_safe(data.get("email"), LIMITS["email"]).lower(),
        student=data.get("student") if data.get("student") in {"yes", "no", "soon"} else "",
        student_id=_header_safe(data.get("student_id") or data.get("studentId"), LIMITS["student_id"]),
        interests=[_clean(i, 60) for i in list(raw_interests)[:MAX_INTERESTS] if _clean(i, 60)],
        message=_clean(data.get("message"), LIMITS["message"]),
        consented_to_contact=_truthy(data.get("consent")),
        accepted_documents=_truthy(data.get("agree")),
    )

    fields = []
    if not application.name:
        fields.append("name")
    if not EMAIL_PATTERN.match(application.email):
        fields.append("email")
    if not application.accepted_documents:
        fields.append("agree")
    if not application.consented_to_contact:
        fields.append("consent")
    if application.intent == "question" and not application.message:
        fields.append("message")

    if fields:
        return _fail(
            wants_json, 422,
            "Some required details are missing or do not look right. Please check the "
            "highlighted fields.",
            fields,
        )

    if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
        log.error(
            "register: GMAIL_USER and/or GMAIL_APP_PASSWORD are not set, so no mail can be "
            "sent. The application is still saved and visible in the admin."
        )

    application.accepted_at = timezone.now()
    application.save()

    # The application is stored before the emails are attempted, so a mail
    # outage loses a notification but never loses the applicant.
    notified, confirmed, error = send_application_emails(application)
    application.notification_sent = notified
    application.confirmation_sent = confirmed
    application.save(update_fields=["notification_sent", "confirmation_sent"])

    if not notified:
        log.error("register: saved application %s but could not notify the team: %s",
                  application.pk, error)
        return _fail(
            wants_json, 502,
            "We have your message, but our email is having trouble. Someone will still see "
            "it — there is no need to send it again.",
        )

    return _succeed(wants_json, application.email)


def health(request):
    """Cheap liveness probe for nginx, compose and the deploy script."""
    return JsonResponse({"ok": True, "service": "applications"})
