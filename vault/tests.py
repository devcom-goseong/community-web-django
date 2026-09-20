"""The Vault: the gate is the whole of its security, so that is tested hardest."""

from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from events.models import Event

TEST_SETTINGS = {
    "SECURE_SSL_REDIRECT": False,
    "VAULT_PASSWORD": "test-vault-pass",
    "CACHES": {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
}


@override_settings(**TEST_SETTINGS)
class VaultGateTests(TestCase):
    def test_dashboard_is_locked_without_the_password(self):
        self.assertRedirects(self.client.get(reverse("vault:dashboard")), reverse("vault:unlock"))

    def test_wrong_password_does_not_unlock(self):
        resp = self.client.post(reverse("vault:unlock"), {"password": "nope"})
        self.assertContains(resp, "not the vault password")
        self.assertRedirects(self.client.get(reverse("vault:dashboard")), reverse("vault:unlock"))

    def test_correct_password_unlocks(self):
        self.client.post(reverse("vault:unlock"), {"password": "test-vault-pass"})
        resp = self.client.get(reverse("vault:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "The Vault")

    def test_auth_user_is_not_exposed(self):
        # Users belong to the Django admin, not the vault.
        self.client.post(reverse("vault:unlock"), {"password": "test-vault-pass"})
        self.assertEqual(self.client.get(reverse("vault:list", args=["auth.user"])).status_code, 404)


@override_settings(**TEST_SETTINGS)
class VaultCrudTests(TestCase):
    def setUp(self):
        self.client.post(reverse("vault:unlock"), {"password": "test-vault-pass"})
        start = timezone.now() + timedelta(days=5)
        self.event = Event.objects.create(
            title="Vault Test Event", summary="A test.",
            starts_at=start, ends_at=start + timedelta(hours=1),
            visibility=Event.Visibility.PUBLIC, status=Event.Status.PUBLISHED)

    def test_list_shows_the_object(self):
        resp = self.client.get(reverse("vault:list", args=["events.event"]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Vault Test Event")

    def test_edit_page_loads(self):
        self.assertEqual(
            self.client.get(reverse("vault:edit", args=["events.event", self.event.pk])).status_code, 200)

    def test_delete_removes_the_object(self):
        resp = self.client.post(reverse("vault:delete", args=["events.event", self.event.pk]))
        self.assertRedirects(resp, reverse("vault:list", args=["events.event"]))
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_delete_needs_the_vault_unlocked(self):
        self.client.get(reverse("vault:lock"))
        resp = self.client.post(reverse("vault:delete", args=["events.event", self.event.pk]))
        self.assertRedirects(resp, reverse("vault:unlock"))
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())
