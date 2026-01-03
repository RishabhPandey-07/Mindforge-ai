from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import DailyLog

@login_required
def log_list(request):
    logs = DailyLog.objects.filter(user=request.user)
    return render(request, "daily_logs/log_list.html", {"logs": logs})


@login_required
def add_log(request):
    if request.method == "POST":
        title = request.POST.get("title")
        content = request.POST.get("content")

        DailyLog.objects.create(
            user=request.user,
            title=title,
            content=content
        )
        return redirect("log_list")

    return render(request, "daily_logs/add_log.html")
