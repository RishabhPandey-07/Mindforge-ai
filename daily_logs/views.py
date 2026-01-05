from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import DailyLog
from collections import Counter
from .ai_service import generate_log_summary

import re


@login_required
def log_list(request):
    logs = DailyLog.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "daily_logs/log_list.html", {"logs": logs})


@login_required
def add_log(request):
    if request.method == "POST":
        content = request.POST.get("content")
        messages.success(request, "Daily log added successfully.")


        if content:
            DailyLog.objects.create(
                user=request.user,
                content=content
            )
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
        messages.success(request, "Daily log updated.")


        if content:
            log.content = content
            log.save()
            return redirect("daily_logs:log_list")

    return render(request, "daily_logs/edit_log.html", {"log": log})

@login_required
def ai_insights(request):
    logs = DailyLog.objects.filter(user=request.user)

    # If user has no logs
    if not logs.exists():
        return render(request, "daily_logs/ai_insights.html", {
            "message": "No logs available to analyze."
        })

    full_text = " ".join(log.content for log in logs)

    # Clean text: lowercase, remove symbols
    words = re.findall(r"\b\w+\b", full_text.lower())

    common_words = Counter(words).most_common(5)

    context = {
        "total_logs": logs.count(),
        "last_log_date": logs.latest("created_at").created_at,
        "common_words": common_words,
    }

    return render(request, "daily_logs/ai_insights.html", context)

@login_required
def ai_summary(request):
    logs = DailyLog.objects.filter(user=request.user)

    if not logs.exists():
        return render(request, "daily_logs/ai_summary.html", {
            "error": "No logs available for AI analysis."
        })

    combined_text = "\n".join(log.content for log in logs)

    ai_result = generate_log_summary(combined_text)

    return render(request, "daily_logs/ai_summary.html", {
        "ai_result": ai_result
    })


