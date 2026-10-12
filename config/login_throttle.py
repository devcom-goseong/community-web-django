"""Stops the password pages being guessed at.

Three pages on this site take a password: the member sign-in, the Django admin
and the Vault. Before this, all three would answer an unlimited number of
wrong guesses as fast as the server could render the form, which on a machine
that sees tens of thousands of password attempts a week is the easiest way in
that we were leaving open.

It is one middleware rather than a check written into each view because the
admin's sign-in is Django's own and we do not want a patched copy of it. What
the three pages do have in common is their answer: every one of them redirects
when the password was right and re-renders the form when it was wrong, so the
status code says which happened and this file needs to know nothing else about
them.

Pages are found by URL name, so moving the admin (it does not live at /admin/)
or the Vault does not quietly switch the protection off. A name that does not
resolve is skipped: the Vault can be turned off entirely, and nothing here
should stop the site from starting if it is.
"""

import logging

from django.conf import settings
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from .ratelimit import clear_sign_in_failures, record_sign_in_failure, sign_in_blocked

log = logging.getLogger(__name__)

# url name, counter, the field naming the account, one password shared by all
GATES = (
    ("accounts:login", "signin", "username", False),
    ("admin:login", "admin", "username", False),
    ("vault:unlock", "vault", None, True),
)

REDIRECTS = frozenset((301, 302, 303, 307, 308))


class SignInThrottle:
    def __init__(self, get_response):
        self.get_response = get_response
        self._gates = None

    @property
    def gates(self):
        """{path: (counter, field, shared)}, worked out once, on first use.

        Not in __init__: reversing a URL imports the whole URL configuration,
        and doing that while the middleware is being built happens early
        enough to be fragile.
        """
        if self._gates is None:
            found = {}
            for name, scope, field, shared in GATES:
                try:
                    found[reverse(name)] = (scope, field, shared)
                except NoReverseMatch:
                    log.debug("sign-in throttle: nothing named %s on this site", name)
            self._gates = found
        return self._gates

    def __call__(self, request):
        gate = self.gates.get(request.path) if request.method == "POST" else None
        if gate is None:
            return self.get_response(request)
        scope, field, shared = gate

        account = ""
        if field:
            try:
                account = (request.POST.get(field) or "").strip().lower()[:254]
            except Exception:
                # An unreadable or oversized body is not worth a 500. Without
                # the address this still counts the connection's failures.
                account = ""

        reason = sign_in_blocked(request, scope, account=account, shared=shared)
        if reason:
            # No address and no password in the log. Which account was being
            # tried is not ours to write down, and nginx already records who
            # connected.
            log.warning("refused a sign-in: %s is over the limit for one %s", scope, reason)
            return self.refuse(request)

        response = self.get_response(request)
        if response.status_code in REDIRECTS:
            clear_sign_in_failures(request, scope, account=account)
        else:
            record_sign_in_failure(request, scope, account=account, shared=shared)
        return response

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
