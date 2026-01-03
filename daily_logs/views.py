from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import DailyLog

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


