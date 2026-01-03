from django.urls import path
from . import views
app_name = "daily_logs" 
urlpatterns = [
    path("", views.log_list, name="log_list"),
    path("add/", views.add_log, name="add_log"),
    path("delete/<int:log_id>/", views.delete_log, name="delete_log"),

]
