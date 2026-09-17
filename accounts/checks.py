"""Deployment checks for settings that fail quietly rather than loudly.

A wrong APP_URL does not break anything you would notice by clicking around:
every page works, because pages build their links from the request. It only
shows up in the emails sent without a request — the event reminders — which
would all link to localhost. CI runs `check --deploy`, so this stops that at
build time instead of after the first reminder goes out.
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security, deploy=True)
def app_url_is_real(app_configs, **kwargs):
    host = (urlsplit(settings.APP_URL).hostname or "").lower()
    if settings.DEBUG or host not in {"", "localhost", "127.0.0.1", "0.0.0.0"}:
        return []
    return [Warning(
        "APP_URL points at this machine, so links in emails sent without a request (event "
        "reminders) will not work for anyone else.",
        hint="Set APP_URL to the public address of this app, e.g. https://community.example.org.",
        id="accounts.W001",
    )]


@register(Tags.security, deploy=True)
def app_url_is_https(app_configs, **kwargs):
    if settings.DEBUG or urlsplit(settings.APP_URL).scheme == "https":
        return []
    return [Warning(
        "APP_URL does not use https, so links in emails would send people to an insecure address.",
        hint="Use the https:// address nginx serves.",
        id="accounts.W002",
    )]
