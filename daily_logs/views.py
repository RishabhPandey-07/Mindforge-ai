"""
views.py

Handles all HTTP request/response logic for daily logs,
AI insights, caching, and mood trends.

Important rules followed here:
- No business logic outside view functions
- No duplicate views
- Clean imports
"""

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.utils.timezone import now

from collections import Counter
import re

from .models import DailyLog, MoodTrend
from .ai_service import generate_log_summary


# --------------------------------------------------
# DAILY LOG CRUD
# --------------------------------------------------

@login_required
def log_list(request):
    logs = DailyLog.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "daily_logs/log_list.html", {"logs": logs})


@login_required
def add_log(request):
    if request.method == "POST":
        content = request.POST.get("content")

        if content:
            DailyLog.objects.create(
                user=request.user,
                content=content
            )
            messages.success(request, "Daily log added successfully.")
            return redirect("daily_logs:log_list")

    return render(request, "daily_logs/add_log.html")


@login_required
def delete_log(request, log_id):
    log = get_object_or_404(DailyLog, id=log_id, user=request.user)

    if request.method == "POST":
        log.delete()
        messages.success(request, "Daily log deleted.")

    return redirect("daily_logs:log_list")


@login_required
def edit_log(request, log_id):
    log = get_object_or_404(DailyLog, id=log_id, user=request.user)

    if request.method == "POST":
        content = request.POST.get("content")

        if content:
            log.content = content
            log.save()
            messages.success(request, "Daily log updated.")
            return redirect("daily_logs:log_list")

    return render(request, "daily_logs/edit_log.html", {"log": log})


# --------------------------------------------------
# BASIC (NON-AI) INSIGHTS
# --------------------------------------------------

@login_required
def ai_insights(request):
    logs = DailyLog.objects.filter(user=request.user)

    if not logs.exists():
        return render(request, "daily_logs/ai_insights.html", {
            "message": "No logs available to analyze."
        })

    full_text = " ".join(log.content for log in logs)

    # Clean text and extract words
    words = re.findall(r"\b\w+\b", full_text.lower())
    common_words = Counter(words).most_common(5)

    context = {
        "total_logs": logs.count(),
        "last_log_date": logs.latest("created_at").created_at,
        "common_words": common_words,
    }

    return render(request, "daily_logs/ai_insights.html", context)


# --------------------------------------------------
# AI SUMMARY + CACHING + MOOD TREND STORAGE
# --------------------------------------------------

@login_required
def ai_summary(request):
    """
    Generates AI summary using Groq.
    Uses cache to avoid repeated calls.
    Stores daily mood trend (1 entry per day).
    """

    user = request.user
    cache_key = f"ai_summary_user_{user.id}"

    # --------- 1. Cache check ----------
    cached_result = cache.get(cache_key)
    if cached_result:
        return render(request, "daily_logs/ai_summary.html", {
            "ai_result": cached_result,
            "cached": True
        })

    # --------- 2. Fetch logs ----------
    logs = DailyLog.objects.filter(user=user)
    if not logs.exists():
        return render(request, "daily_logs/ai_summary.html", {
            "error": "No logs available for AI analysis."
        })

    combined_text = "\n".join(log.content for log in logs)

    # --------- 3. Call AI ----------
    ai_result = generate_log_summary(combined_text)

    # --------- 4. Save mood trend ----------
    today = now().date()

    MoodTrend.objects.update_or_create(
        user=user,
        created_at=today,
        defaults={
            "mood": ai_result.get("mood", "Unknown"),
            "score": int(ai_result.get("score", 0))
        }
    )

    # --------- 5. Cache result ----------
    cache.set(cache_key, ai_result, timeout=3600)

    return render(request, "daily_logs/ai_summary.html", {
        "ai_result": ai_result,
        "cached": False
    })


# --------------------------------------------------
# MOOD TRENDS VIEW
# --------------------------------------------------

@login_required
def mood_trends(request):
    """
    Displays historical mood trends for the user.
    """

    trends = MoodTrend.objects.filter(user=request.user)

    return render(request, "daily_logs/mood_trends.html", {
        "trends": trends
    })
