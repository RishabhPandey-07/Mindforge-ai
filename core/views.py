from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.utils.timezone import now
from datetime import timedelta

from daily_logs.models import DailyLog, MoodTrend


@never_cache
@login_required
def dashboard(request):
    """
    Dashboard shows:
    - Today's summary
    - Writing streak
    """

    user = request.user

    # -------------------------------
    # LOG SUMMARY
    # -------------------------------
    logs = DailyLog.objects.filter(user=user).order_by("-created_at")

    last_log = logs.first()
    total_logs = logs.count()

    today = now().date()

    mood_today = MoodTrend.objects.filter(
        user=user,
        created_at=today
    ).first()

    # -------------------------------
    # STREAK CALCULATION
    # -------------------------------
    streak = 0
    current_day = today

    # Get all unique log dates (fast & clean)
    log_dates = set(
        DailyLog.objects.filter(user=user)
        .dates("created_at", "day")
    )

    # Count consecutive days backwards
    while current_day in log_dates:
        streak += 1
        current_day -= timedelta(days=1)

    context = {
        "last_log": last_log,
        "total_logs": total_logs,
        "mood_today": mood_today,
        "streak": streak,
    }

    return render(request, "core/dashboard.html", context)
