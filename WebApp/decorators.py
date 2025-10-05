from functools import wraps
from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.urls import reverse, NoReverseMatch

def admin_required(view_func):
    """
    Restrict view to admin users only (based on session 'user_role').
    Redirects to login if not admin.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        role = request.session.get("user_role", "").lower()

        if role == "admin":
            return view_func(request, *args, **kwargs)

        # If not logged in, redirect to login
        if not request.user.is_authenticated:
            try:
                return redirect(reverse("login"))  # safer, uses URL name
            except NoReverseMatch:
                return redirect("/login/")  # fallback

        # If logged in but not admin, block access
        return HttpResponseForbidden("You are not authorized to view this page.")

    return wrapper
