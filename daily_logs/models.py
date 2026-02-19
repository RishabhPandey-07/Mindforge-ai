from django.db import models
from django.contrib.auth.models import User


class DailyLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.created_at.strftime('%d %b %Y')}"


class MoodTrend(models.Model):
    """
    Stores AI-generated mood analysis for a user on a specific day.

    Why this model exists:
    - Avoid recomputing AI analysis every time
    - Enable weekly/monthly trend analysis
    - Allow future graphs and reports
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="mood_trends"
    )

    mood = models.CharField(
        max_length=50,
        help_text="Mood label like Happy, Stressed, Calm"
    )

    score = models.IntegerField(
        help_text="Mood intensity score from 1 to 10"
    )

    created_at = models.DateField(
        auto_now_add=True,
        help_text="Date when this mood was recorded"
    )

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.mood} ({self.score})"


class WeeklyReview(models.Model):
    """
    Stores one AI-generated weekly review per user/week.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="weekly_reviews",
    )
    week_start = models.DateField(help_text="Start date of week (Monday)")
    wins = models.TextField(blank=True)
    challenges = models.TextField(blank=True)
    focus = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start"]
        unique_together = ("user", "week_start")

    def __str__(self):
        return f"{self.user.username} weekly review {self.week_start}"


class ProductEvent(models.Model):
    """
    Basic product analytics event stream for retention and funnel metrics.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="product_events",
    )
    name = models.CharField(max_length=100, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.name}"
