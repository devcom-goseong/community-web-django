"""A small per-connection rate limiter, shared by every form on the site.

It lives here rather than inside one app because the join form, sign-up,
event registration and the directory search all use it.

Two things about it are deliberate.

The IP address is hashed and only ever lives in the cache, never in the
database, because the published privacy notice says the address is not stored.

The address is taken from what nginx saw, not from what the client claims. The
earlier version read the *first* entry of X-Forwarded-For, but that entry is
whatever the client put in the header: nginx appends the real address to the
end of any value it is sent. So anyone could get a fresh allowance on every
request by sending a made-up header, and none of the limits limited anything.
nginx sets X-Real-IP to the address of the connection itself, which a client
cannot influence, and that is read first.
"""

import hashlib
import logging

from django.conf import settings
from django.core.cache import cache

log = logging.getLogger(__name__)


def client_ip(request):
    """The address of whoever actually connected.

    In production every request arrives through nginx, which sets X-Real-IP
    from the socket and appends the socket address to X-Forwarded-For. Without
    nginx in front (local runs, tests) REMOTE_ADDR is already the client.
    """
    real_ip = request.META.get("HTTP_X_REAL_IP", "").strip()
    if real_ip:
        return real_ip
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        # The last hop is the one our own proxy added. Everything before it
        # came from the client and cannot be trusted.
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def rate_limited(request, scope="form", limit=None, window=None):
    """True if this connection has used up its allowance for `scope`.

    `scope` keeps separate counters for separate things, so creating an
    account does not spend the allowance for sending the join form. On a shared
    university connection that would otherwise make people starve each other
    for reasons none of them could see.

    `limit` and `window` default to the form settings. Actions a real person
    repeats legitimately, such as registering for several events in a row, pass
    a higher limit.
    """
    ip = client_ip(request)
    if not ip:
        return False
    limit = settings.RATE_LIMIT_MAX if limit is None else limit
    window = settings.RATE_LIMIT_WINDOW_SECONDS if window is None else window

    digest = hashlib.sha256(ip.encode("utf-8")).hexdigest()[:32]
    key = f"ratelimit:{scope}:{digest}"
    try:
        cache.get_or_set(key, 0, window)
        hits = cache.incr(key)
    except ValueError:
        cache.set(key, 1, window)
        hits = 1
    except Exception:  # a cache problem must not lock real people out
        log.exception("rate limiter unavailable; allowing the request")
        return False
    return hits > limit


# --- failed sign-ins --------------------------------------------------------
#
# The limiter above counts requests, which is right for a form anyone may send
# once but wrong for a sign-in page: a member who signs in correctly on their
# phone and then on their laptop has done nothing wrong, and shutting them out
# for it would be our mistake, not theirs. So the sign-in pages count only
# failures, and getting the password right clears the count.
#
# Two counters run at once, because they stop different things:
#
#   by connection   one host trying many passwords. This is the ordinary case
#                   and what the server actually sees all day.
#   by account      many hosts trying one account. A per-connection limit can
#                   never catch that, because every host stays under it.
#
# The second one has a cost worth writing down. Someone who knows a member's
# email address can keep that address locked for the length of the window by
# failing on purpose. Against that: the limit is set high enough that a person
# fumbling their own password will not reach it, the lock lasts minutes rather
# than for ever, and a member who is locked out can still set a new password
# through the emailed reset link. Leaving one known address open to thousands
# of guesses is the worse of the two.
#
# A third counter is used only by the Vault, which has one shared password
# instead of accounts. There the two counters above are not enough: a thousand
# hosts trying ten passwords each stays under both. So the Vault also counts
# every failure together, whatever it came from.


def _fail_key(scope, kind, value):
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]
    return f"signinfail:{scope}:{kind}:{digest}"


def _failures(key):
    try:
        return cache.get(key, 0) or 0
    except Exception:  # same rule as above: a broken cache locks nobody out
        log.exception("cache unavailable; not counting failed sign-ins")
        return 0


def _bump(key, window):
    try:
        cache.get_or_set(key, 0, window)
        return cache.incr(key)
    except ValueError:  # it expired between those two calls
        cache.set(key, 1, window)
        return 1
    except Exception:
        log.exception("cache unavailable; a failed sign-in went uncounted")
        return 0


def sign_in_blocked(request, scope, account="", shared=False):
    """Why this attempt should be refused, or "" to let it through.

    The reason is a word for the log. Nothing here says which part of the
    password was wrong, or whether the account exists, because the caller
    refuses the attempt before the password is looked at.
    """
    ip = client_ip(request)
    if ip and _failures(_fail_key(scope, "from", ip)) >= settings.LOGIN_FAIL_MAX:
        return "connection"
    if account and _failures(_fail_key(scope, "for", account)) >= settings.LOGIN_FAIL_ACCOUNT_MAX:
        return "account"
    if shared and _failures(_fail_key(scope, "all", "")) >= settings.LOGIN_FAIL_SHARED_MAX:
        return "shared password"
    return ""


def record_sign_in_failure(request, scope, account="", shared=False):
    """Remember that a password was wrong."""
    window = settings.LOGIN_FAIL_WINDOW_SECONDS
    ip = client_ip(request)
    if ip:
        _bump(_fail_key(scope, "from", ip), window)
    if account:
        _bump(_fail_key(scope, "for", account), window)
    if shared:
        _bump(_fail_key(scope, "all", ""), window)


def clear_sign_in_failures(request, scope, account=""):
    """Forget the failures of whoever just got in.

    The shared counter is deliberately left alone. It is there to notice a
    flood against one password from many places, and one success in the middle
    of a flood does not mean the flood has stopped.
    """
    ip = client_ip(request)
    keys = [_fail_key(scope, "from", ip)] if ip else []
    if account:
        keys.append(_fail_key(scope, "for", account))
    if not keys:
        return
    try:
        cache.delete_many(keys)
    except Exception:
        log.exception("cache unavailable; failed sign-ins were not cleared")
