from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from .models import Profile
from django.contrib.auth import authenticate, login, logout

def user_signup(request):
    """
    Handles new user registration.
    Creates a user and logs them in immediately.
    """

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # Basic validation
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("signup")

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect("signup")

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Auto login after signup
        login(request, user)

        return redirect("dashboard")

    return render(request, "accounts/signup.html")


def user_login(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid username or password")
            return redirect("login")

    return render(request, "accounts/login.html")

def user_logout(request):
    logout(request)
    return redirect("login")
