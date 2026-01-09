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
