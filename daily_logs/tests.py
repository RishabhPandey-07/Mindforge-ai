from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse

from .models import DailyLog
from accounts.models import Subscription


class DailyLogsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="loguser",
            password="StrongPass#123",
            email="loguser@example.com",
            is_active=True,
        )

    def test_log_list_requires_login(self):
        response = self.client.get(reverse("daily_logs:log_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_add_log_creates_entry(self):
        self.client.login(username="loguser", password="StrongPass#123")
        response = self.client.post(
            reverse("daily_logs:add_log"),
            data={"content": "Today I felt focused and calm."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(DailyLog.objects.filter(user=self.user).exists())

    def test_weekly_review_shows_error_without_logs(self):
        self.client.login(username="loguser", password="StrongPass#123")
        response = self.client.get(reverse("daily_logs:weekly_review"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("pricing"))

    def test_chat_shows_error_without_logs(self):
        self.client.login(username="loguser", password="StrongPass#123")
        response = self.client.post(
            reverse("daily_logs:chat_logs"),
            data={"question": "Why was I upset today?"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("pricing"))

    def test_ai_summary_redirects_free_user_to_pricing(self):
        DailyLog.objects.create(user=self.user, content="I felt calm today.")
        self.client.login(username="loguser", password="StrongPass#123")
        response = self.client.get(reverse("daily_logs:ai_summary"))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("pricing"))
