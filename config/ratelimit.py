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
