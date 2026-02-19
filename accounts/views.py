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

from daily_logs.models import ProductEvent


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
