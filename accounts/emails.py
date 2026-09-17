"""The welcome email with its confirmation link, and the approval email.

The confirmation token is a signed value rather than a row in a table: there is
nothing to expire by hand, nothing to clean up, and a link that has been used
once still works, which is what someone who clicks twice expects.

The approval email deliberately does not contain the community's invite links.
Emails get forwarded and archived in places the community cannot see; the links
are on the member's account page, behind sign-in, where they can be changed if
one ever leaks.
"""

import logging

from django.conf import settings
from django.core import signing
from django.urls import reverse

from content.emails import build_message, html_layout, send_each

log = logging.getLogger(__name__)

SALT = "accounts.verify-email"
MAX_AGE_SECONDS = 3 * 24 * 60 * 60  # three days


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


def _absolute(request, path):
    # From a request, the address the person actually used. Without one — an
    # admin action run in a script, say — this app's own configured address.
    # Never PUBLIC_SITE_URL: that is the static site, which has no /account/.
    if request is not None:
        return request.build_absolute_uri(path)
    return f"{settings.APP_URL}{path}"


def send_welcome_email(member, request=None):
    """Tell them the account exists and ask them to confirm the address.

    Returns True if it went out. A failure is logged and swallowed: the account
    has already been created, and the member can ask for another link from their
    own page, so an SMTP problem must not turn into an error on a sign-up that
    actually worked.
    """
    user = member.user
    url = _absolute(request, reverse("accounts:verify", args=[make_token(user)]))
    policies = _absolute(request, reverse("content:page", args=["privacy"]))

    lines = [
        f"Hello {member.display_name}, your account for the {settings.TEAM_NAME} has been "
        "created.",
        "Confirm your email address with the button below. The link works for three days; "
        "if it runs out, sign in and ask for a new one.",
    ]
    text = (
        "\n\n".join(lines)
        + f"\n\nConfirm your address:\n{url}\n\n"
        f"The privacy notice explains what the account holds: {policies}\n\n"
        "If you did not create this account, ignore this email and nothing further happens.\n\n"
        f"--\n{settings.TEAM_NAME}\n"
    )
    html = html_layout(
        "Confirm your email address", lines, button=("Confirm my address", url),
        footnote="If you did not create this account, ignore this email and nothing further "
                 "happens.",
    )
    message = build_message(
        user.email, f"Confirm your email address — {settings.TEAM_NAME}", text, html)
    return all(send_each([message], "welcome email"))


def send_approval_email(member, request=None):
    """Tell a member they have been approved, and where to go next."""
    account = _absolute(request, reverse("accounts:dashboard"))
    lines = [
        f"Hello {member.display_name}, you are now a member of the {settings.TEAM_NAME}.",
        "Sign in to your account to find the invite links to the community's chats, sign up "
        "for events, and set up your profile so other members can find you.",
        "Your profile stays private until you choose otherwise.",
    ]
    text = "\n\n".join(lines) + f"\n\nYour account: {account}\n\n--\n{settings.TEAM_NAME}\n"
    html = html_layout("Welcome in", lines, button=("Go to your account", account))
    message = build_message(
        member.user.email, f"You are a member — {settings.TEAM_NAME}", text, html)
    return all(send_each([message], "approval email"))
