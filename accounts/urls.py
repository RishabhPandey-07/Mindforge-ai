from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.user_signup, name="signup"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),
    path("verify/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("pricing/", views.pricing, name="pricing"),
    path("billing/", views.billing, name="billing"),
    path("billing/success/", views.billing_success, name="billing_success"),
    path("billing/cancel/", views.billing_cancel, name="billing_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
