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
from django.conf import settings
from django.urls import reverse

from collections import Counter
import re
from datetime import timedelta

from .models import DailyLog, MoodTrend, WeeklyReview, ProductEvent
from .ai_service import chat_with_logs
from .tasks import generate_ai_summary_task, generate_weekly_review_task
from accounts.subscriptions import has_feature


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


def _track_event(user, name: str, metadata: dict | None = None):
    if not settings.PRODUCT_EVENT_TRACKING_ENABLED:
        return
    ProductEvent.objects.create(
        user=user,
        name=name,
        metadata=metadata or {},
    )


def _queue_task(task, *args):
    """
    Queue a background task. Returns True on success.
    """
    try:
        task.delay(*args)
        return True
    except Exception:
        return False


def _require_feature(request, feature_name: str):
    if has_feature(request.user, feature_name):
        return None
    messages.info(request, "This feature is available on Pro and Team plans.")
    return redirect(reverse("pricing"))


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
            log = DailyLog.objects.create(
                user=request.user,
                content=content
            )
            _track_event(
                request.user,
                "log_created",
                {"log_id": log.id, "content_chars": len(content)},
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
        _track_event(request.user, "log_deleted", {"log_id": log_id})
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
            _track_event(
                request.user,
                "log_edited",
                {"log_id": log.id, "content_chars": len(content)},
            )
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
    feature_redirect = _require_feature(request, "ai_summary")
    if feature_redirect:
        return feature_redirect
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
        _track_event(user, "ai_summary_viewed", {"cached": True})
        return render(request, "daily_logs/ai_summary.html", {
            "ai_result": cached_result,
            "mood": cached_result.get("mood", "Unknown"),
            "score": _safe_score(cached_result.get("score", 0)),
            "summary": cached_result.get("summary", ""),
            "suggestion": cached_result.get("suggestion", ""),
            "cached": True
        })

    pending_key = f"{cache_key}:pending"
    if cache.get(pending_key):
        return render(request, "daily_logs/ai_summary.html", {
            "processing": True,
            "cached": False,
        })

    queued = _queue_task(generate_ai_summary_task, user.id, latest_log_id)
    if not queued:
        return render(request, "daily_logs/ai_summary.html", {
            "error": "AI worker is not reachable. Start Celery worker and retry.",
        })

    cache.set(pending_key, True, timeout=300)
    _track_event(user, "ai_summary_queued", {"last_log_id": latest_log_id})
    return render(request, "daily_logs/ai_summary.html", {
        "processing": True,
        "cached": False,
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


@never_cache
@login_required
def weekly_review(request):
    user = request.user
    feature_redirect = _require_feature(request, "weekly_review")
    if feature_redirect:
        return feature_redirect
    today = now().date()
    week_start = today - timedelta(days=today.weekday())
    week_logs = DailyLog.objects.filter(
        user=user,
        created_at__date__gte=week_start,
    ).order_by("created_at")

    if not week_logs.exists():
        return render(request, "daily_logs/weekly_review.html", {
            "error": "No logs found for this week. Add a few entries first.",
            "week_start": week_start,
        })

    latest_log = week_logs.last()
    latest_log_id = latest_log.id if latest_log else 0
    cache_key = f"weekly_review_user_{user.id}_{week_start}_lastlog_{latest_log_id}"
    cached_result = cache.get(cache_key)
    if cached_result:
        _track_event(user, "weekly_review_viewed", {"cached": True})
        return render(request, "daily_logs/weekly_review.html", {
            "review": cached_result,
            "week_start": week_start,
            "cached": True,
        })

    pending_key = f"{cache_key}:pending"
    if cache.get(pending_key):
        return render(request, "daily_logs/weekly_review.html", {
            "processing": True,
            "week_start": week_start,
            "cached": False,
        })

    queued = _queue_task(generate_weekly_review_task, user.id, week_start.isoformat(), latest_log_id)
    if not queued:
        return render(request, "daily_logs/weekly_review.html", {
            "error": "AI worker is not reachable. Start Celery worker and retry.",
            "week_start": week_start,
        })

    cache.set(pending_key, True, timeout=300)
    _track_event(user, "weekly_review_queued", {"week_start": week_start.isoformat()})
    return render(request, "daily_logs/weekly_review.html", {
        "processing": True,
        "week_start": week_start,
        "cached": False,
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
    evidence = None
    next_step = None
    error = None

    feature_redirect = _require_feature(request, "mind_chat")
    if feature_redirect:
        return feature_redirect

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
                result = chat_with_logs(formatted_logs, question)
                answer = result.get("answer")
                evidence = result.get("evidence")
                next_step = result.get("next_step")
                _track_event(
                    request.user,
                    "chat_asked",
                    {"question_chars": len(question), "answered": bool(answer)},
                )
            except RuntimeError as exc:
                error = str(exc)
                _track_event(
                    request.user,
                    "chat_asked",
                    {"question_chars": len(question), "answered": False},
                )

    return render(request, "daily_logs/chat.html", {
        "answer": answer,
        "evidence": evidence,
        "next_step": next_step,
        "error": error
    })
