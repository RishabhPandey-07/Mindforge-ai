from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse


class DashboardTests(TestCase):
    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_dashboard_loads_for_authenticated_user(self):
        user = User.objects.create_user(
            username="tester",
            password="StrongPass#123",
            email="tester@example.com",
            is_active=True,
        )
        self.client.login(username="tester", password="StrongPass#123")

        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome back")
