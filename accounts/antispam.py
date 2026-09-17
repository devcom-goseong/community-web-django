"""Quiet bot defences for the sign-up form.

The sign-up form is open to the world and, on success, creates an account and
sends a confirmation email. That makes it a standing invitation to bots that
read the page, fill every field they can find and submit. Two cheap, well-worn
checks turn most of them away without ever troubling a real person:

  * a honeypot field that is hidden from people but not from a bot that fills
    in everything it sees, and
  * a timestamp planted when the page is rendered, so a submission that arrives
    within a few seconds — faster than anyone reads the page and chooses a
    password — can be recognised as automated.

The timestamp is *signed* rather than trusted as sent, for the same reason the
rate limiter reads the address nginx saw and not the one the client claims: a
value the client can write is a value a bot can forge. A missing or unsigned
timestamp is treated leniently — it is allowed through for the honeypot to
judge — so that a legitimate post which never rendered the page (a test, a
scripted client) is not turned away for the absence alone.

Nothing here stores anything or looks at the address: it reads two fields off
the submission and returns a verdict. A caller that gets `True` should behave
exactly as it would on success, but make no account and send no mail, so a bot
learns nothing it can adapt to.
"""

import logging
import time

from django.core import signing

log = logging.getLogger(__name__)

# Named like an ordinary field a bot would want to fill; hidden from people in
# the template. A real submission always leaves it empty.
HONEYPOT_FIELD = "company"
TIMESTAMP_FIELD = "ts"
# Nobody reads the page, types a name and address and sets a password this fast.
MIN_SECONDS = 3
_SALT = "accounts.signup.timestamp"


def new_timestamp():
    """A signed 'rendered now' token to plant in the form on each render."""
    return signing.Signer(salt=_SALT).sign(str(int(time.time())))


def _too_fast(value):
    """True only for a validly signed timestamp younger than ``MIN_SECONDS``.

    A missing or tampered token returns False on purpose: the honeypot is then
    the check that decides, and a real post that carried no token is not
    punished for that alone.
    """
    if not value:
        return False
    try:
        issued = int(signing.Signer(salt=_SALT).unsign(value))
    except (signing.BadSignature, ValueError):
        return False
    return (time.time() - issued) < MIN_SECONDS


def is_bot_signup(request):
    """Return ``(is_bot, reason)`` for a sign-up POST."""
    if request.POST.get(HONEYPOT_FIELD, "").strip():
        return True, "honeypot"
    if _too_fast(request.POST.get(TIMESTAMP_FIELD, "")):
        return True, "too-fast"
    return False, ""
