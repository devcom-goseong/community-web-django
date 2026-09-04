"""The welcome email, and the signed link that verifies an address.

The token is a signed value rather than a row in a table: there is nothing to
expire by hand, nothing to clean up, and a link that has been used once still
works, which is what someone who clicks twice expects.
"""

import logging

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives, get_connection
from django.urls import reverse
from django.utils.html import escape

log = logging.getLogger(__name__)

SALT = "accounts.verify-email"
MAX_AGE_SECONDS = 3 * 24 * 60 * 60  # three days

# The identity, so the email looks like the site it came from.
NAVY = "#062350"
MUTED = "#4e617e"
PAPER = "#f7f3ea"
RULE = "#d5d6d4"


def make_token(user):
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=SALT)


def read_token(token, max_age=MAX_AGE_SECONDS):
    """Return the payload, or None if the link is expired, altered or stale.

    The address is part of the signed payload and checked against the account
    at the point of use, so a link stops working if the address it was issued
    for has since changed. Otherwise an old link would verify a new address
    that nobody has proved control of.
    """
    try:
        return signing.loads(token, salt=SALT, max_age=max_age)
    except signing.SignatureExpired:
        log.info("verification link expired")
    except signing.BadSignature:
        log.warning("verification link failed its signature check")
    return None


def _verify_url(request, user):
    path = reverse("accounts:verify", args=[make_token(user)])
    if request is not None:
        return request.build_absolute_uri(path)
    return settings.PUBLIC_SITE_URL.rstrip("/") + path


def send_welcome_email(member, request=None):
    """Tell them the account exists and ask them to confirm the address.

    Returns True if it went out. A failure is logged and swallowed: the
    account has already been created, and the member can ask for another link
    from their own page, so an SMTP problem must not turn into a 500 on a
    sign-up that actually worked.
    """
    user = member.user
    url = _verify_url(request, user)
    site = settings.PUBLIC_SITE_URL.rstrip("/")

    text = (
        f"Hello {member.display_name},\n\n"
        "Your account for the KDU Developer Community has been created.\n\n"
        "Confirm your email address by opening this link:\n\n"
        f"{url}\n\n"
        "The link works for three days. If it expires, sign in and ask for a new one.\n\n"
        "What you agreed to when you signed up:\n"
        f"  Community rules   {site}/rules.html\n"
        f"  Terms             {site}/terms.html\n"
        f"  Privacy notice    {site}/privacy.html\n\n"
        "If you did not create this account, ignore this email and nothing further happens.\n\n"
        "--\nKDU Developer Community\n"
    )

    html = f"""<div style="font-family:Georgia,'Times New Roman',serif;color:{NAVY};line-height:1.6;max-width:600px;background:{PAPER};padding:32px">
  <p style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:{MUTED};margin:0 0 8px">
    KDU Developer Community
  </p>
  <h1 style="font-size:24px;margin:0 0 20px;color:{NAVY}">Confirm your email address</h1>
  <p style="font-size:16px;margin:0 0 20px">Hello {escape(member.display_name)}, your account has been created.</p>
  <p style="margin:0 0 28px">
    <a href="{escape(url)}" style="display:inline-block;background:{NAVY};color:{PAPER};text-decoration:none;padding:14px 26px;font-size:14px;letter-spacing:.08em;text-transform:uppercase">Confirm my address</a>
  </p>
  <p style="font-size:14px;color:{MUTED};margin:0 0 20px">
    The link works for three days. If it expires, sign in and ask for a new one.
  </p>
  <p style="font-size:14px;color:{MUTED};border-top:1px solid {RULE};padding-top:16px;margin:0">
    You agreed to the <a href="{site}/rules.html" style="color:{NAVY}">community rules</a>,
    the <a href="{site}/terms.html" style="color:{NAVY}">terms</a> and the
    <a href="{site}/privacy.html" style="color:{NAVY}">privacy notice</a>.
    If you did not create this account, ignore this email.
  </p>
</div>"""

    try:
        connection = get_connection()
        message = EmailMultiAlternatives(
            subject="Confirm your email address — KDU Developer Community",
            body=text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
            connection=connection,
        )
        message.attach_alternative(html, "text/html")
        message.send()
        return True
    except Exception:
        log.exception("could not send the welcome email to member %s", member.pk)
        return False
