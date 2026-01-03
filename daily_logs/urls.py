from django.urls import path
from .views import log_list, add_log
app_name = "daily_logs" 
urlpatterns = [
    path("", log_list, name="log_list"),
    path("add/", add_log, name="add_log"),
]
