# from django.shortcuts import render, redirect
# from django.contrib.auth.models import User
# from django.contrib import messages
# from .models import Profile
# from django.contrib.auth import authenticate, login, logout

# def user_signup(request):
#     """
#     Handles new user registration.
#     Creates a user and logs them in immediately.
#     """

#     if request.method == "POST":
#         username = request.POST.get("username")
#         email = request.POST.get("email")
#         password = request.POST.get("password")

#         # Basic validation
#         if not username or not password:
#             messages.error(request, "Username and password are required.")
#             return redirect("signup")

#         # Check if username already exists
#         if User.objects.filter(username=username).exists():
#             messages.error(request, "Username already taken.")
#             return redirect("signup")

#         # Create user
#         user = User.objects.create_user(
#             username=username,
#             email=email,
#             password=password
#         )

#         # Auto login after signup
#         login(request, user)

#         return redirect("dashboard")

#     return render(request, "accounts/signup.html")


# def user_login(request):
#     if request.method == "POST":
#         username = request.POST.get("username")
#         password = request.POST.get("password")

#         user = authenticate(request, username=username, password=password)

#         if user is not None:
#             login(request, user)
#             return redirect("dashboard")
#         else:
#             messages.error(request, "Invalid username or password")
#             return redirect("login")

#     return render(request, "accounts/login.html")

# def user_logout(request):
#     logout(request)
#     return redirect("login")

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache


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

        # Authenticate user credentials
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Successful login
            login(request, user)
            return redirect("dashboard")
        else:
            # Invalid credentials
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
        if not username or not password:
            messages.error(request, "Username and password are required.")
            return redirect("signup")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return redirect("signup")

        # Create user (password is hashed automatically)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Auto-login after signup
        login(request, user)
        return redirect("dashboard")

    return render(request, "accounts/signup.html")


@never_cache
def user_logout(request):
    """
    Logs out the user.

    - Clears session
    - Redirects to login page
    - Back button will NOT show protected pages
    """

    logout(request)
    return redirect("login")
