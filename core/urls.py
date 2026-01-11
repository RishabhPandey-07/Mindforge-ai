from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),  # 👈 EMPTY PATH
    path("home/", views.home, name="home"),
]

