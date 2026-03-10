from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.shortcuts import render, redirect
from django.core.cache import cache
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.conf import settings
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from daily_logs.models import ProductEvent
from .models import Subscription
from .subscriptions import get_or_create_subscription
from .plan_catalog import PLAN_CATALOG
from .stripe_service import (
    cancel_subscription,
    create_checkout_session,
    stripe_is_configured,
    build_webhook_event,
    sync_subscription_from_stripe,
)


def _track_event(user, name: str, metadata: dict | None = None):
    if not settings.PRODUCT_EVENT_TRACKING_ENABLED:
        return
    ProductEvent.objects.create(
        user=user,
        name=name,
        metadata=metadata or {},
    )


@never_cache
def user_login(request):
    """
    Handles user login.

    never_cache:
    - Prevents browser from caching login-protected pages
    - Stops back-button access after logout
    """

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        ip = request.META.get("REMOTE_ADDR", "unknown")
        rate_key = f"login_attempts:{ip}:{username}"
        locked_key = f"login_locked:{ip}:{username}"

        if cache.get(locked_key):
            messages.error(request, "Too many attempts. Try again later.")
            return render(request, "accounts/login.html")

        # Inform if account exists but is not active (email not verified)
        if User.objects.filter(username=username, is_active=False).exists():
            messages.error(request, "Please verify your email before logging in.")
            return render(request, "accounts/login.html")

        # Authenticate user credentials
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Successful login
            login(request, user)
            cache.delete(rate_key)
            _track_event(user, "user_logged_in")
            return redirect("dashboard")
        else:
            # Invalid credentials
            attempts = cache.get(rate_key, 0) + 1
            cache.set(rate_key, attempts, timeout=900)
            if attempts >= 5:
                cache.set(locked_key, True, timeout=900)
            messages.error(request, "Invalid username or password.")

    return render(request, "accounts/login.html")


@never_cache
def user_signup(request):
    """
    Handles user registration.

    - Creates a new user
    - Logs them in immediately
    """

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Basic validation
        if not username or not password or not email:
            messages.error(request, "Username, email, and password are required.")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("signup")

        # Validate password using Django validators
        try:
            validate_password(password)
        except Exception as exc:
            for msg in getattr(exc, "messages", [str(exc)]):
                messages.error(request, msg)
            return redirect("signup")

        # Create user (password is hashed automatically)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.is_active = False
        user.save()
        get_or_create_subscription(user)

        # Send verification email
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        verify_path = reverse("verify_email", kwargs={"uidb64": uid, "token": token})
        scheme = "https" if request.is_secure() or settings.SECURE_SSL_REDIRECT else "http"
        verify_url = f"{scheme}://{request.get_host()}{verify_path}"

        send_mail(
            subject="Verify your MindForge AI account",
            message=(
                "Welcome to MindForge AI!\n\n"
                "Please verify your email to activate your account:\n"
                f"{verify_url}\n\n"
                "If you did not sign up, you can ignore this email."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        messages.success(request, "Check your email to verify your account.")
        _track_event(user, "signup_started")
        return redirect("login")

    return render(request, "accounts/signup.html")


@never_cache
def user_logout(request):
    """
    Logs out the user.

    - Clears session
    - Redirects to login page
    - Back button will NOT show protected pages
    """

    if request.user.is_authenticated:
        _track_event(request.user, "user_logged_out")
    logout(request)
    return redirect("login")


@never_cache
def verify_email(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (User.DoesNotExist, ValueError, TypeError):
        user = None

    if user and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        _track_event(user, "email_verified")
        messages.success(request, "Email verified. You can log in now.")
        return redirect("login")

    messages.error(request, "Verification link is invalid or expired.")
    return redirect("login")


@never_cache
def pricing(request):
    current_plan = None
    if request.user.is_authenticated:
        current_plan = get_or_create_subscription(request.user).plan
    return render(
        request,
        "accounts/pricing.html",
        {
            "plans": PLAN_CATALOG,
            "current_plan": current_plan,
            "billing_mode": settings.BILLING_MODE,
        },
    )


@never_cache
@login_required
def billing(request):
    subscription = get_or_create_subscription(request.user)

    if request.method == "POST":
        requested_plan = request.POST.get("plan")
        valid_plans = {
            Subscription.PLAN_FREE,
            Subscription.PLAN_PRO,
            Subscription.PLAN_TEAM,
        }
        if requested_plan in valid_plans:
            if requested_plan == Subscription.PLAN_FREE:
                if stripe_is_configured():
                    try:
                        cancel_subscription(subscription)
                    except RuntimeError as exc:
                        messages.error(request, str(exc))
                        return redirect("billing")
                else:
                    subscription.plan = Subscription.PLAN_FREE
                    subscription.status = Subscription.STATUS_ACTIVE
                    subscription.current_period_end = None
                    subscription.save(update_fields=["plan", "status", "current_period_end", "updated_at"])
                _track_event(request.user, "plan_changed", {"plan": requested_plan})
                messages.success(request, "Plan changed to Free.")
                return redirect("billing")

            subscription.plan = requested_plan
            subscription.save(update_fields=["plan", "updated_at"])

            if not stripe_is_configured():
                subscription.status = Subscription.STATUS_ACTIVE
                subscription.save(update_fields=["status", "updated_at"])
                _track_event(request.user, "plan_changed", {"plan": requested_plan, "mode": "local"})
                messages.success(request, f"Plan changed to {subscription.get_plan_display()}.")
                return redirect("billing")

            try:
                session = create_checkout_session(
                    subscription=subscription,
                    success_url=request.build_absolute_uri(reverse("billing_success")),
                    cancel_url=request.build_absolute_uri(reverse("billing_cancel")),
                )
            except RuntimeError as exc:
                messages.error(request, str(exc))
                return redirect("billing")

            _track_event(request.user, "checkout_started", {"plan": requested_plan})
            return redirect(session.url, permanent=False)

        messages.error(request, "Invalid plan selected.")

    return render(
        request,
        "accounts/billing.html",
        {
            "subscription": subscription,
            "stripe_configured": stripe_is_configured(),
            "billing_mode": settings.BILLING_MODE,
        },
    )


@never_cache
@login_required
def billing_success(request):
    messages.success(request, "Checkout completed. Your plan will update as soon as Stripe confirms payment.")
    return redirect("billing")


@never_cache
@login_required
def billing_cancel(request):
    messages.info(request, "Checkout was canceled. Your plan has not changed.")
    return redirect("billing")


@csrf_exempt
def stripe_webhook(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed."}, status=405)

    try:
        event = build_webhook_event(
            payload=request.body,
            signature=request.META.get("HTTP_STRIPE_SIGNATURE", ""),
        )
    except Exception:
        return JsonResponse({"detail": "Invalid webhook signature."}, status=400)

    event_type = event["type"]
    if event_type in {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }:
        obj = event["data"]["object"]
        stripe_subscription = obj
        if event_type == "checkout.session.completed" and obj.get("subscription"):
            try:
                import stripe

                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe_subscription = stripe.Subscription.retrieve(obj["subscription"])
            except Exception:
                return JsonResponse({"detail": "Unable to fetch subscription."}, status=400)

        subscription = sync_subscription_from_stripe(stripe_subscription)
        if subscription:
            _track_event(
                subscription.user,
                "stripe_subscription_synced",
                {
                    "plan": subscription.plan,
                    "status": subscription.status,
                    "event_type": event_type,
                },
            )

    return HttpResponse(status=200)
