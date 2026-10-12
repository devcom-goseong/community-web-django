"""Stops the password pages being guessed at.

Three pages on this site take a password: the member sign-in, the Django admin
and the Vault. Before this, all three would answer an unlimited number of
wrong guesses as fast as the server could render the form, which on a machine
that sees tens of thousands of password attempts a week is the easiest way in
that we were leaving open.

The work is split in two, and the split is the whole design:

  refusing    the middleware, which has to run before the password is looked
              at and so cannot know anything about the outcome.
  counting    Django's own `user_login_failed` and `user_logged_in` signals,
              which say whether a password was right without anybody having
              to guess, and the Vault's own view, which is ours to edit.

The first version counted by reading the status code instead, treating any
redirect as a success. That is wrong, and wrong in the direction that matters:
with DEBUG off Django answers an http request with a redirect to https before
the view runs at all, so a single request over http would have cleared the
count and the limit could be walked around for ever. Anything that infers "the
password was right" from the shape of a response has the same hole in it
somewhere, which is why nothing here does.

Pages are found by URL name, so moving the admin (it does not live at /admin/)
or the Vault does not quietly switch the protection off. A name that does not
resolve is skipped: the Vault can be turned off entirely, and nothing here
should stop the site from starting if it is.
"""

import functools
import logging

from django.conf import settings
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from .ratelimit import clear_sign_in_failures, record_sign_in_failure, sign_in_blocked

log = logging.getLogger(__name__)

SIGNIN = "signin"
ADMIN = "admin"
VAULT = "vault"

# url name, counter, the field naming the account, one password shared by all
GATES = (
    ("accounts:login", SIGNIN, "username", False),
    ("admin:login", ADMIN, "username", False),
    ("vault:unlock", VAULT, None, True),
)


@functools.lru_cache(maxsize=1)
def gates():
    """{path: (counter, field, shared)}.

    Worked out once per process. URL names do not change while the site is
    running, and reversing them at import time happens early enough to be
    fragile.
    """
    found = {}
    for name, scope, field, shared in GATES:
        try:
            found[reverse(name)] = (scope, field, shared)
        except NoReverseMatch:
            log.debug("sign-in throttle: nothing named %s on this site", name)
    return found


def gate_for(request):
    """The gate this request is knocking on, or None."""
    if request is None:
        return None
    return gates().get(request.path)


def account_in(request, field):
    """The address or username being tried, tidied for use as a counter key."""
    if not field:
        return ""
    try:
        return (request.POST.get(field) or "").strip().lower()[:254]
    except Exception:
        # An unreadable or oversized body is not worth a 500. Without the
        # address the per-connection counter still does its job.
        return ""


class SignInThrottle:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        gate = gate_for(request) if request.method == "POST" else None
        if gate is None:
            return self.get_response(request)
        scope, field, shared = gate

        reason = sign_in_blocked(
            request, scope, account=account_in(request, field), shared=shared)
        if not reason:
            return self.get_response(request)

        # No address and no password in the log. Which account was being tried
        # is not ours to write down, and nginx already records who connected.
        log.warning("refused a sign-in: %s is over the limit for one %s", scope, reason)
        return self.refuse(request)

    def refuse(self, request):
        window = settings.LOGIN_FAIL_WINDOW_SECONDS
        response = render(request, "429.html", {
            "page_title": "Too many attempts",
            "page_description": "Too many sign-in attempts from here.",
            "minutes": max(1, round(window / 60)),
            "noindex": True,
        }, status=429)
        response["Retry-After"] = str(window)
        return response


def note_failure(sender, credentials=None, request=None, **kwargs):
    """Django says a password was wrong.

    Both the member sign-in and the admin's own sign-in end up here, which is
    why the admin needs no patched copy of its view. Django has already taken
    the password out of `credentials` before sending this.
    """
    gate = gate_for(request)
    if gate is None:
        return  # authenticate() is called in places that are not a sign-in page
    scope, field, shared = gate
    record_sign_in_failure(request, scope, account=account_in(request, field), shared=shared)


def note_success(sender, request=None, user=None, **kwargs):
    """Django says somebody got in, so what went before no longer counts.

    Keyed on what was typed rather than on the account that was found: a
    superuser whose username is not their email address would otherwise clear
    a counter nobody was filling.
    """
    gate = gate_for(request)
    if gate is None:
        return
    scope, field, _shared = gate
    clear_sign_in_failures(request, scope, account=account_in(request, field))


# Connected here, where the receivers are, and on import of the middleware -
# which Django builds before it handles anything, so no sign-in can slip past
# while they are not listening. dispatch_uid keeps a reload from doubling them.
user_login_failed.connect(note_failure, dispatch_uid="signin-throttle-failure")
user_logged_in.connect(note_success, dispatch_uid="signin-throttle-success")
