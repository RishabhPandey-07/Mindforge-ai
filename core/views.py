from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.conf import settings
from django.shortcuts import render
from django.http import HttpResponseForbidden
from django.views.decorators.cache import never_cache
from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Count
import json

from daily_logs.models import DailyLog, MoodTrend, WeeklyReview, ProductEvent


def _track_event(user, name: str, metadata: dict | None = None):
    if not settings.PRODUCT_EVENT_TRACKING_ENABLED:
        return
    ProductEvent.objects.create(
        user=user,
        name=name,
        metadata=metadata or {},
    )


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
    latest_weekly_review = WeeklyReview.objects.filter(user=user).first()

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
        "latest_weekly_review": latest_weekly_review,
    }
    _track_event(user, "dashboard_viewed")

    return render(request, "core/dashboard.html", context)


@never_cache
@login_required
def product_analytics(request):
    if not request.user.is_staff:
        return HttpResponseForbidden("Staff access required.")

    today = now().date()
    last_14_days = today - timedelta(days=13)
    last_30_days = today - timedelta(days=29)

    events_30 = ProductEvent.objects.filter(created_at__date__gte=last_30_days)

    daily_counts_qs = (
        events_30.values("created_at__date")
        .annotate(total_events=Count("id"), active_users=Count("user", distinct=True))
        .order_by("created_at__date")
    )
    daily_map = {row["created_at__date"]: row for row in daily_counts_qs}

    date_cursor = last_14_days
    labels = []
    events_series = []
    dau_series = []
    while date_cursor <= today:
        labels.append(date_cursor.strftime("%d %b"))
        row = daily_map.get(date_cursor, {})
        events_series.append(row.get("total_events", 0))
        dau_series.append(row.get("active_users", 0))
        date_cursor += timedelta(days=1)

    top_events = (
        events_30.values("name")
        .annotate(total=Count("id"))
        .order_by("-total")[:8]
    )

    week_start = today - timedelta(days=today.weekday())
    week_events = ProductEvent.objects.filter(created_at__date__gte=week_start).count()
    wau = ProductEvent.objects.filter(created_at__date__gte=today - timedelta(days=6)).values("user").distinct().count()

    signup_events = ProductEvent.objects.filter(name="signup_started")
    retained = 0
    for event in signup_events:
        target_day = event.created_at.date() + timedelta(days=7)
        returned = ProductEvent.objects.filter(
            user=event.user,
            created_at__date=target_day,
        ).exists()
        if returned:
            retained += 1
    d7_rate = round((retained / signup_events.count()) * 100, 1) if signup_events.exists() else 0

    _track_event(request.user, "product_analytics_viewed")
    context = {
        "total_users": User.objects.count(),
        "week_events": week_events,
        "wau": wau,
        "d7_rate": d7_rate,
        "top_events": top_events,
        "chart_labels": json.dumps(labels),
        "chart_events": json.dumps(events_series),
        "chart_dau": json.dumps(dau_series),
    }
    return render(request, "core/product_analytics.html", context)
