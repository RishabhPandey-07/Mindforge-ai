from datetime import date

from celery import shared_task
from django.core.cache import cache
from django.utils.timezone import now

from .ai_service import generate_log_summary, generate_weekly_review
from .models import DailyLog, MoodTrend, WeeklyReview


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_ai_summary_task(self, user_id: int, latest_log_id: int):
    logs = DailyLog.objects.filter(user_id=user_id)
    if not logs.exists():
        return {"status": "no_logs"}

    current_latest = logs.order_by("-created_at").first()
    current_latest_id = current_latest.id if current_latest else 0
    cache_key = f"ai_summary_user_{user_id}_lastlog_{latest_log_id}"
    pending_key = f"{cache_key}:pending"

    if current_latest_id != latest_log_id:
        cache.delete(pending_key)
        return {"status": "stale"}

    combined_text = "\n".join(log.content for log in logs)
    ai_result = generate_log_summary(combined_text)
    today = now().date()

    MoodTrend.objects.update_or_create(
        user_id=user_id,
        created_at=today,
        defaults={
            "mood": ai_result.get("mood", "Unknown"),
            "score": int("".join(filter(str.isdigit, str(ai_result.get("score", "0")))) or 0),
        },
    )
    cache.set(cache_key, ai_result, timeout=3600)
    cache.delete(pending_key)
    return {"status": "ok"}


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def generate_weekly_review_task(self, user_id: int, week_start_iso: str, latest_log_id: int):
    week_start = date.fromisoformat(week_start_iso)
    week_logs = DailyLog.objects.filter(
        user_id=user_id,
        created_at__date__gte=week_start,
    ).order_by("created_at")

    if not week_logs.exists():
        return {"status": "no_logs"}

    current_latest = week_logs.last()
    current_latest_id = current_latest.id if current_latest else 0
    cache_key = f"weekly_review_user_{user_id}_{week_start}_lastlog_{latest_log_id}"
    pending_key = f"{cache_key}:pending"
    if current_latest_id != latest_log_id:
        cache.delete(pending_key)
        return {"status": "stale"}

    combined_text = "\n".join(log.content for log in week_logs)
    review = generate_weekly_review(combined_text)

    WeeklyReview.objects.update_or_create(
        user_id=user_id,
        week_start=week_start,
        defaults={
            "wins": review.get("wins", ""),
            "challenges": review.get("challenges", ""),
            "focus": review.get("focus", ""),
        },
    )
    cache.set(cache_key, review, timeout=3600)
    cache.delete(pending_key)
    return {"status": "ok"}
