"""The two emails a submission produces.

Same intent as the Netlify function this replaces: the team gets a
notification they can reply to directly, and the applicant gets a
confirmation with a record of what they accepted.

Both are sent over a single SMTP connection. Opening two was what made the
old serverless version occasionally exceed its time limit, and there is no
reason to repeat it here.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.utils.html import escape

log = logging.getLogger(__name__)

STUDENT_LABELS = {"yes": "Yes", "no": "No", "soon": "Starting soon", "": "Not answered"}


def _rows(application):
    return [
        ("Name", application.name),
        ("Email", application.email),
        ("KDU student", STUDENT_LABELS.get(application.student, "Not answered")),
        ("Student ID", application.student_id or "—"),
        ("Interests", ", ".join(application.interests) if application.interests else "—"),
        ("Reason", "Question" if application.is_question else "Membership application"),
        ("Accepted rules, terms, privacy", "Yes" if application.accepted_documents else "No"),
        ("Consented to be contacted", "Yes" if application.consented_to_contact else "No"),
        ("Received", application.created_at.strftime("%Y-%m-%d %H:%M %Z")),
    ]


def _notification(application, admin_url):
    rows = _rows(application)
    text = (
        "\n".join(f"{label}: {value}" for label, value in rows)
        + "\n\nMessage:\n"
        + (application.message or "(no message)")
        + f"\n\n--\nReview it in the admin: {admin_url}\n"
        + "Reply directly to this email to answer them."
    )
    row_html = "\n".join(
        f'<tr><td style="padding:8px 16px 8px 0;border-bottom:1px solid #d4d4d4;'
        f'color:#6a6a6a;white-space:nowrap;vertical-align:top">{escape(label)}</td>'
        f'<td style="padding:8px 0;border-bottom:1px solid #d4d4d4;color:#141414">'
        f"{escape(str(value))}</td></tr>"
        for label, value in rows
    )
    html = f"""<div style="font-family:Helvetica,Arial,sans-serif;color:#141414;line-height:1.6;max-width:640px">
  <p style="font-family:monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#6a6a6a;margin:0 0 8px">
    {"New question" if application.is_question else "New membership application"}
  </p>
  <h1 style="font-size:22px;margin:0 0 20px;color:#0d0d0d">{escape(application.name)}</h1>
  <table style="border-collapse:collapse;width:100%;font-size:14px">{row_html}</table>
  <p style="font-family:monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#6a6a6a;margin:24px 0 8px">Message</p>
  <div style="white-space:pre-wrap;border-left:2px solid #0d0d0d;padding:4px 0 4px 16px;font-size:15px">{escape(application.message or "(no message)")}</div>
  <p style="font-size:13px;color:#6a6a6a;margin-top:28px;border-top:1px solid #d4d4d4;padding-top:12px">
    <a href="{admin_url}">Review it in the admin</a> — or reply to this email to answer them directly.
  </p>
</div>"""
    return text, html


def _confirmation(application):
    site = settings.PUBLIC_SITE_URL
    first_name = (application.name.split() or ["there"])[0]
    summary_lines = [
        f"Reason: {'A question' if application.is_question else 'Membership application'}",
        f"Name: {application.name}",
        f"Email: {application.email}",
        f"KDU student: {STUDENT_LABELS.get(application.student, 'Not answered')}",
    ]
    if application.interests:
        summary_lines.append("Interests: " + ", ".join(application.interests))
    summary_lines.append(
        "Accepted the community rules, terms and privacy notice on "
        + application.created_at.strftime("%Y-%m-%d %H:%M %Z")
    )
    summary = "\n".join(summary_lines)

    text = f"""Hi {first_name},

Thanks for your interest in the {settings.TEAM_NAME}. We have your message, and
someone on the leadership team will read it and get back to you.

Here is what you sent us:

{summary}

{("Your message:" + chr(10) + application.message + chr(10) + chr(10)) if application.message else ""}You can read what you agreed to at any time:
  Rules:   {site}/rules.html
  Terms:   {site}/terms.html
  Privacy: {site}/privacy.html

If anything above is wrong, just reply to this email and tell us.

— The {settings.TEAM_NAME} leadership team
Kyungdong University, South Korea
{site}

We keep your details so the leadership team can review your application, and we
do not share them outside that team. Ask us to delete them and we will."""

    html = f"""<div style="font-family:Helvetica,Arial,sans-serif;color:#141414;line-height:1.65;max-width:600px">
  <p style="font-family:monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#6a6a6a;margin:0 0 8px">{escape(settings.TEAM_NAME)}</p>
  <h1 style="font-size:24px;margin:0 0 20px;color:#0d0d0d">Thanks, {escape(first_name)} — we have it.</h1>
  <p style="margin:0 0 16px">Someone on the leadership team will read what you wrote and get back to you.</p>
  <p style="font-family:monospace;font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#6a6a6a;margin:28px 0 8px">What you sent us</p>
  <div style="white-space:pre-wrap;border-left:2px solid #0d0d0d;padding:4px 0 4px 16px;font-size:14px">{escape(summary)}</div>
  {f'<div style="white-space:pre-wrap;border-left:2px solid #d4d4d4;padding:4px 0 4px 16px;margin-top:16px;font-size:14px;color:#6a6a6a">{escape(application.message)}</div>' if application.message else ""}
  <p style="margin:24px 0 0">You agreed to the <a href="{site}/rules.html">community rules</a>,
    <a href="{site}/terms.html">terms</a> and <a href="{site}/privacy.html">privacy notice</a>.
    If anything above is wrong, just reply to this email.</p>
  <p style="margin:24px 0 0;color:#6a6a6a">— The {escape(settings.TEAM_NAME)} leadership team<br>Kyungdong University, South Korea</p>
</div>"""
    return text, html


def send_application_emails(application, admin_url=""):
    """Send both messages over one connection.

    Returns (notification_sent, confirmation_sent, error). The notification is
    the one that matters; a failed confirmation is logged and swallowed,
    because by then the team already has the application.
    """
    admin_url = admin_url or f"{settings.PUBLIC_SITE_URL}"
    reply_to_applicant = f"{application.name} <{application.email}>"
    subject = (
        f"[KDU Dev] Question from {application.name}"
        if application.is_question
        else f"[KDU Dev] Membership application — {application.name}"
    )

    notification_text, notification_html = _notification(application, admin_url)
    confirmation_text, confirmation_html = _confirmation(application)

    connection = None
    notified = confirmed = False
    error = None
    try:
        connection = get_connection()
        connection.open()

        team = EmailMultiAlternatives(
            subject=subject,
            body=notification_text,
            to=[settings.TEAM_INBOX],
            reply_to=[reply_to_applicant],
            connection=connection,
        )
        team.attach_alternative(notification_html, "text/html")
        notified = bool(team.send())

        try:
            applicant = EmailMultiAlternatives(
                subject=f"Thanks for your interest in the {settings.TEAM_NAME}",
                body=confirmation_text,
                to=[f"{application.name} <{application.email}>"],
                reply_to=[settings.TEAM_INBOX],
                connection=connection,
            )
            applicant.attach_alternative(confirmation_html, "text/html")
            confirmed = bool(applicant.send())
        except Exception as exc:  # noqa: BLE001 - the team already has it
            log.exception("could not send the applicant confirmation")
            error = str(exc)

    except Exception as exc:  # noqa: BLE001 - reported to the caller
        log.exception("could not send the team notification")
        error = str(exc)
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:  # noqa: BLE001
                pass

    return notified, confirmed, error
