from django.urls import path
from . import views
app_name = "daily_logs" 
urlpatterns = [
    path("", views.log_list, name="log_list"),
    path("add/", views.add_log, name="add_log"),
    path("delete/<int:log_id>/", views.delete_log, name="delete_log"),
    path("edit/<int:log_id>/", views.edit_log, name="edit_log"),
    path("ai/", views.ai_insights, name="ai_insights"),
    path("ai-summary/", views.ai_summary, name="ai_summary"),
    path("trends/", views.mood_trends, name="mood_trends"),
    path("chat/", views.chat_logs, name="chat_logs"),

]
