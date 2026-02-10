"""
views.py

Handles all HTTP request/response logic for daily logs,
AI insights, caching, chat, and mood trends.

Security rules:
- login_required protects private pages
- never_cache prevents back-button access after logout
"""

from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from django.utils.timezone import now

from collections import Counter
import re

from .models import DailyLog, MoodTrend
from .ai_service import generate_log_summary, chat_with_logs


def _safe_score(score_value) -> int:
    """
    Best-effort parsing for AI score output.
    Accepts "7", "7/10", "Score: 7", etc.
    """
    if score_value is None:
        return 0
    match = re.search(r"\d+", str(score_value))
    if not match:
        return 0
    score = int(match.group(0))
    return max(0, min(score, 10))


# --------------------------------------------------
# DAILY LOG CRUD
# --------------------------------------------------

@never_cache
@login_required
def log_list(request):
    logs = DailyLog.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "daily_logs/log_list.html", {"logs": logs})


@never_cache
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


@never_cache
@login_required
def delete_log(request, log_id):
    log = get_object_or_404(DailyLog, id=log_id, user=request.user)

    if request.method == "POST":
        log.delete()
        messages.success(request, "Daily log deleted.")

    return redirect("daily_logs:log_list")


@never_cache
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

@never_cache
@login_required
def ai_insights(request):
    logs = DailyLog.objects.filter(user=request.user)

    if not logs.exists():
        return render(request, "daily_logs/ai_insights.html", {
            "message": "No logs available to analyze."
        })

    full_text = " ".join(log.content for log in logs)

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

@never_cache
@login_required
def ai_summary(request):
    """
    Generates AI summary.
    Uses cache to avoid repeated calls.
    Stores one mood trend per day.
    """

    user = request.user
    # 1. Fetch logs
    logs = DailyLog.objects.filter(user=user)
    if not logs.exists():
        return render(request, "daily_logs/ai_summary.html", {
            "error": "No logs available for AI analysis."
        })

    # 2. Cache check (keyed by latest log)
    latest_log = logs.order_by("-created_at").first()
    latest_log_id = latest_log.id if latest_log else 0
    cache_key = f"ai_summary_user_{user.id}_lastlog_{latest_log_id}"
    cached_result = cache.get(cache_key)
    if cached_result:
        return render(request, "daily_logs/ai_summary.html", {
            "ai_result": cached_result,
            "mood": cached_result.get("mood", "Unknown"),
            "score": _safe_score(cached_result.get("score", 0)),
            "summary": cached_result.get("summary", ""),
            "suggestion": cached_result.get("suggestion", ""),
            "cached": True
        })

    combined_text = "\n".join(log.content for log in logs)

    # 3. AI call
    try:
        ai_result = generate_log_summary(combined_text)
    except RuntimeError as exc:
        return render(request, "daily_logs/ai_summary.html", {
            "error": str(exc)
        })

    # 4. Save mood trend
    today = now().date()

    MoodTrend.objects.update_or_create(
        user=user,
        created_at=today,
        defaults={
            "mood": ai_result.get("mood", "Unknown"),
            "score": _safe_score(ai_result.get("score", 0))
        }
    )

    # 5. Cache result
    cache.set(cache_key, ai_result, timeout=3600)

    return render(request, "daily_logs/ai_summary.html", {
        "ai_result": ai_result,
        "mood": ai_result.get("mood", "Unknown"),
        "score": _safe_score(ai_result.get("score", 0)),
        "summary": ai_result.get("summary", ""),
        "suggestion": ai_result.get("suggestion", ""),
        "cached": False
    })


# --------------------------------------------------
# MOOD TRENDS VIEW
# --------------------------------------------------

@never_cache
@login_required
def mood_trends(request):
    """
    Displays historical mood trends and prepares graph data.
    """

    trends = MoodTrend.objects.filter(user=request.user)

    dates = [t.created_at.strftime("%d %b") for t in trends]
    scores = [t.score for t in trends]

    return render(request, "daily_logs/mood_trends.html", {
        "trends": trends,
        "dates": dates,
        "scores": scores,
    })


# --------------------------------------------------
# CHAT WITH LOGS
# --------------------------------------------------

@never_cache
@login_required
def chat_logs(request):
    """
    Handles AI chat based on user's logs.
    """

    answer = None
    error = None

    if request.method == "POST":
        question = request.POST.get("question")
        logs = DailyLog.objects.filter(user=request.user)

        if not question:
            error = "Please enter a question."
        elif not logs.exists():
            error = "No logs available to answer your question yet."
        else:
            log_items = list(
                logs.order_by("-created_at")
                .values_list("created_at", "content")
            )
            formatted_logs = [
                (dt.strftime("%Y-%m-%d"), content)
                for dt, content in log_items
            ]
            try:
                answer = chat_with_logs(formatted_logs, question)
            except RuntimeError as exc:
                error = str(exc)

    return render(request, "daily_logs/chat.html", {
        "answer": answer,
        "error": error
    })
