import json
import time

from django.core import mail
from django.test import TestCase, override_settings

from .models import Application

JSON = "application/json"


def payload(**over):
    body = {
        "intent": "join",
        "name": "Test Student",
        "email": "Test.Student@Example.com",
        "student": "yes",
        "studentId": "20260001",
        "interests": ["Programming", "Design"],
        "message": "I want to learn web development.",
        "consent": "yes",
        "agree": "yes",
        "website": "",
        "ts": str(int((time.time() - 5) * 1000)),
    }
    body.update(over)
    return json.dumps(body)


# Pinned so the suite behaves the same however the environment is configured.
# Without SECURE_SSL_REDIRECT off, the test client's http:// requests are
# redirected before they ever reach a view.
@override_settings(
    SECURE_SSL_REDIRECT=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    GMAIL_USER="kdu@example.com",
    EMAIL_HOST_USER="kdu@example.com",
    EMAIL_HOST_PASSWORD="app-password",
    TEAM_INBOX="team@example.com",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class RegisterEndpointTests(TestCase):
    url = "/api/register"

    def post(self, body=None, content_type=JSON, **extra):
        return self.client.post(self.url, body if body is not None else payload(),
                                content_type=content_type, **extra)

    # --- method and shape -------------------------------------------------
    def test_get_is_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_valid_submission_is_stored_and_emailed(self):
        response = self.post(REMOTE_ADDR="10.0.0.2")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

        application = Application.objects.get()
        self.assertEqual(application.name, "Test Student")
        self.assertEqual(application.email, "test.student@example.com", "email is lowercased")
        self.assertEqual(application.interests, ["Programming", "Design"])
        self.assertTrue(application.accepted_documents)
        self.assertTrue(application.consented_to_contact)
        self.assertIsNotNone(application.accepted_at)
        self.assertEqual(application.status, Application.Status.NEW)

        self.assertEqual(len(mail.outbox), 2)
        team, applicant = mail.outbox
        self.assertEqual(team.to, ["team@example.com"])
        self.assertIn("test.student@example.com", team.reply_to[0])
        self.assertIn("Membership application", team.subject)
        self.assertIn("Accepted rules, terms, privacy: Yes", team.body)
        self.assertIn("test.student@example.com", applicant.to[0])
        self.assertIn("Thanks for your interest", applicant.subject)
        self.assertIn("rules.html", applicant.body)
        self.assertTrue(application.notification_sent)
        self.assertTrue(application.confirmation_sent)

    # --- validation -------------------------------------------------------
    def test_missing_required_fields_are_named(self):
        response = self.post(payload(name="", email="nope", consent="", agree=""),
                             REMOTE_ADDR="10.0.0.3")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(set(response.json()["fields"]), {"name", "email", "agree", "consent"})
        self.assertEqual(Application.objects.count(), 0, "nothing invalid is stored")
        self.assertEqual(len(mail.outbox), 0)

    def test_question_without_a_message_is_rejected(self):
        response = self.post(payload(intent="question", message=""), REMOTE_ADDR="10.0.0.4")
        self.assertEqual(response.status_code, 422)
        self.assertIn("message", response.json()["fields"])

    def test_agreement_is_required_on_the_server(self):
        response = self.post(payload(agree=""), REMOTE_ADDR="10.0.0.5")
        self.assertEqual(response.status_code, 422)
        self.assertIn("agree", response.json()["fields"])
        self.assertEqual(Application.objects.count(), 0)

    # --- spam protection --------------------------------------------------
    def test_honeypot_looks_successful_but_stores_nothing(self):
        response = self.post(payload(website="http://spam.example"), REMOTE_ADDR="10.0.0.6")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"], "a bot should learn nothing from the response")
        self.assertEqual(Application.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_instant_submission_is_rejected(self):
        response = self.post(payload(ts=str(int(time.time() * 1000))), REMOTE_ADDR="10.0.0.7")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Application.objects.count(), 0)

    def test_missing_timestamp_is_allowed_for_the_no_javascript_path(self):
        self.assertEqual(self.post(payload(ts="0"), REMOTE_ADDR="10.0.0.8").status_code, 200)

    def test_rate_limit_throttles_a_burst(self):
        for _ in range(5):
            self.post(REMOTE_ADDR="10.0.0.99")
        self.assertEqual(self.post(REMOTE_ADDR="10.0.0.99").status_code, 429)

    def test_ip_address_is_never_stored(self):
        self.post(REMOTE_ADDR="203.0.113.7")
        stored = json.dumps([
            {k: str(v) for k, v in vars(a).items() if not k.startswith("_")}
            for a in Application.objects.all()
        ])
        self.assertNotIn("203.0.113.7", stored,
                         "the privacy notice says the IP is not stored, so it must not be")

    # --- injection and escaping ------------------------------------------
    def test_crlf_is_stripped_from_header_fields(self):
        self.post(payload(name="Evil\r\nBcc: victim@example.com"), REMOTE_ADDR="10.0.0.10")
        team = mail.outbox[0]
        self.assertNotIn("\n", team.subject)
        self.assertNotIn("\r", team.subject)
        self.assertNotIn("victim@example.com", team.to)

    def test_html_is_escaped_in_the_email_body(self):
        self.post(payload(message="<script>alert(1)</script>"), REMOTE_ADDR="10.0.0.11")
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn("<script>", html)

    # --- no-JavaScript path ----------------------------------------------
    def test_form_encoded_post_returns_a_page(self):
        response = self.client.post(
            self.url,
            {"intent": "join", "name": "Form Only", "email": "form@example.com",
             "student": "no", "interests": ["Design", "Not sure yet"],
             "message": "Posted without JavaScript.", "consent": "yes", "agree": "yes",
             "ts": "0"},
            REMOTE_ADDR="10.0.0.12",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response["Content-Type"])
        self.assertContains(response, "Thank you")
        application = Application.objects.get()
        self.assertEqual(application.interests, ["Design", "Not sure yet"])

    # --- resilience -------------------------------------------------------
    def test_application_survives_a_mail_failure(self):
        with self.settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"):
            from unittest import mock
            with mock.patch("applications.emails.get_connection", side_effect=OSError("smtp down")):
                response = self.post(REMOTE_ADDR="10.0.0.13")
        self.assertEqual(response.status_code, 502)
        self.assertIn("message", response.json())
        self.assertEqual(Application.objects.count(), 1,
                         "an email outage must not lose the applicant")
        self.assertFalse(Application.objects.get().notification_sent)


@override_settings(SECURE_SSL_REDIRECT=False)
class HealthTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])


class AdminTests(TestCase):
    def test_applications_cannot_be_created_by_hand(self):
        from django.contrib.admin.sites import site

        from .admin import ApplicationAdmin
        admin_instance = ApplicationAdmin(Application, site)
        self.assertFalse(admin_instance.has_add_permission(None))
