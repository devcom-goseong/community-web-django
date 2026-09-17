"""The one layout every email from the site uses.

Email clients strip stylesheets and most of them will not load a web font, so
the styling is inline and the type is a plain sans-serif stack that is already
on the reader's machine. It is kept deliberately close to the site: soft greys,
rounded corners, one blue for the thing to click, and nothing in capitals.

Every message goes out as plain text with an HTML alternative. The plain text
is written, not generated from the HTML, because it is what some people read.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.defaultfilters import linebreaksbr
from django.utils.html import escape

log = logging.getLogger(__name__)

FONT = "-apple-system,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif"
HEADING = "#2b3140"
TEXT = "#4a5160"
MUTED = "#5f6673"
BLUE = "#2c60c5"
PAGE = "#f5f6f8"
CARD = "#ffffff"
RULE = "#dfe2e7"


def html_layout(heading, paragraphs, button=None, footnote=""):
    """Build the HTML body.

    `paragraphs` are plain strings and are escaped here, so nothing a member
    typed can inject markup into a message. `button` is (label, url).
    """
    body = "".join(
        f'<p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:{TEXT}">'
        f"{linebreaksbr(text, autoescape=True)}</p>"
        for text in paragraphs if text
    )
    action = ""
    if button:
        label, url = button
        action = (
            f'<p style="margin:24px 0 8px"><a href="{escape(url)}" '
            f'style="display:inline-block;background:{BLUE};color:#ffffff;text-decoration:none;'
            f'padding:12px 22px;border-radius:999px;font-size:15px">{escape(label)}</a></p>'
        )
    note = (
        f'<p style="margin:24px 0 0;padding-top:16px;border-top:1px solid {RULE};'
        f'font-size:13px;line-height:1.6;color:{MUTED}">{escape(footnote)}</p>'
        if footnote else ""
    )
    return (
        f'<div style="background:{PAGE};padding:24px 12px;font-family:{FONT}">'
        f'<div style="max-width:560px;margin:0 auto;background:{CARD};border-radius:12px;'
        f'padding:32px 28px;border:1px solid {RULE}">'
        f'<p style="margin:0 0 6px;font-size:13px;color:{MUTED}">{escape(settings.TEAM_NAME)}</p>'
        f'<h1 style="margin:0 0 20px;font-size:22px;line-height:1.3;color:{HEADING}">'
        f"{escape(heading)}</h1>{body}{action}{note}</div></div>"
    )


def build_message(to, subject, text, html, connection=None, attachments=()):
    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
        connection=connection,
    )
    message.attach_alternative(html, "text/html")
    for filename, content, mimetype in attachments:
        message.attach(filename, content, mimetype)
    return message


def send_each(messages, what):
    """Send each message over one shared connection. Returns a success flag per message.

    Messages are sent one at a time rather than as a batch because a batch
    stops at the first failure without saying which messages went out, and the
    callers that care — the reminder job, above all — need to know exactly who
    was reached so nobody is sent the same email twice or missed.

    A failure is logged and swallowed. Every email this site sends follows
    something that has already happened — an account created, a place given —
    and a mail outage must not turn that into an error page or undo it.
    """
    if not messages:
        return []
    try:
        connection = get_connection()
        connection.open()
    except Exception:
        log.exception("could not connect to send %s", what)
        return [False] * len(messages)

    results = []
    try:
        for message in messages:
            message.connection = connection
            try:
                results.append(bool(message.send()))
            except Exception:
                log.exception("could not send one %s", what)
                results.append(False)
    finally:
        try:
            connection.close()
        except Exception:
            log.warning("could not close the mail connection cleanly")
    return results
