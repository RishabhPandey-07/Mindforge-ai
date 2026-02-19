from django.contrib import admin
from .models import DailyLog, MoodTrend, WeeklyReview, ProductEvent

admin.site.register(DailyLog)
admin.site.register(MoodTrend)
admin.site.register(WeeklyReview)
admin.site.register(ProductEvent)
