from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.test import override_settings
from unittest.mock import patch

from .models import Subscription


class AccountsTests(TestCase):
    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)

    def test_signup_creates_inactive_user(self):
        response = self.client.post(
            reverse("signup"),
            data={
                "username": "newuser",
                "email": "newuser@example.com",
                "password": "StrongPass#123",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))
        user = User.objects.get(username="newuser")
        self.assertFalse(user.is_active)
        self.assertEqual(user.subscription.plan, Subscription.PLAN_FREE)

    def test_verify_email_activates_user(self):
        user = User.objects.create_user(
            username="pending",
            email="pending@example.com",
            password="StrongPass#123",
            is_active=False,
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.client.get(
            reverse("verify_email", kwargs={"uidb64": uid, "token": token})
        )

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("login"))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_pricing_page_loads(self):
        response = self.client.get(reverse("pricing"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a plan")

    def test_billing_requires_login(self):
        response = self.client.get(reverse("billing"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_billing_can_change_plan(self):
        user = User.objects.create_user(
            username="billinguser",
            email="billing@example.com",
            password="StrongPass#123",
            is_active=True,
        )
        Subscription.objects.create(user=user)
        self.client.login(username="billinguser", password="StrongPass#123")

        response = self.client.post(reverse("billing"), data={"plan": "pro"})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("billing"))
        user.subscription.refresh_from_db()
        self.assertEqual(user.subscription.plan, Subscription.PLAN_PRO)

    def test_local_billing_fallback_when_stripe_not_configured(self):
        user = User.objects.create_user(
            username="localbilling",
            email="localbilling@example.com",
            password="StrongPass#123",
            is_active=True,
        )
        Subscription.objects.create(user=user)
        self.client.login(username="localbilling", password="StrongPass#123")

        response = self.client.post(reverse("billing"), data={"plan": "team"})

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("billing"))
        user.subscription.refresh_from_db()
        self.assertEqual(user.subscription.plan, Subscription.PLAN_TEAM)

    @override_settings(BILLING_MODE="demo")
    def test_billing_page_explains_demo_mode(self):
        user = User.objects.create_user(
            username="demobilling",
            email="demo@example.com",
            password="StrongPass#123",
            is_active=True,
        )
        Subscription.objects.create(user=user)
        self.client.login(username="demobilling", password="StrongPass#123")

        response = self.client.get(reverse("billing"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demo billing is active")

    @patch("accounts.views.stripe_is_configured", return_value=True)
    @patch("accounts.views.create_checkout_session")
    def test_billing_redirects_to_checkout_when_stripe_enabled(self, mock_session, _mock_configured):
        user = User.objects.create_user(
            username="checkoutuser",
            email="checkout@example.com",
            password="StrongPass#123",
            is_active=True,
        )
        Subscription.objects.create(user=user)
        self.client.login(username="checkoutuser", password="StrongPass#123")

        class DummySession:
            url = "https://checkout.stripe.test/session"

        mock_session.return_value = DummySession()

        response = self.client.post(reverse("billing"), data={"plan": "pro"})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, DummySession.url)
        user.subscription.refresh_from_db()
        self.assertEqual(user.subscription.plan, Subscription.PLAN_PRO)

    @patch("accounts.views.build_webhook_event")
    @patch("accounts.views.sync_subscription_from_stripe")
    def test_stripe_webhook_accepts_subscription_events(self, mock_sync, mock_build_event):
        user = User.objects.create_user(
            username="webhookuser",
            email="webhook@example.com",
            password="StrongPass#123",
            is_active=True,
        )
        subscription = Subscription.objects.create(user=user, stripe_customer_id="cus_123")
        mock_build_event.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "customer": "cus_123",
                    "items": {"data": [{"price": {"id": "price_test"}}]},
                    "status": "active",
                    "id": "sub_123",
                    "current_period_end": None,
                }
            },
        }
        mock_sync.return_value = subscription

        response = self.client.post(
            reverse("stripe_webhook"),
            data=b"payload",
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="sig_test",
        )

        self.assertEqual(response.status_code, 200)
        mock_sync.assert_called_once()
