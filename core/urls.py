from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("analytics/", views.product_analytics, name="product_analytics"),
]
