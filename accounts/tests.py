from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


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
