from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from .models import Profile


def get_user_role(user):
    profile = getattr(user, "profile", None)
    if profile:
        return profile.role
    if user.is_staff:
        return Profile.ROLE_ADMIN
    return Profile.ROLE_STUDENT


def role_required(*allowed_roles):
    """Require authentication and membership in one of the supplied LMS roles."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped_view(request, *args, **kwargs):
            if get_user_role(request.user) in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(request, "You do not have permission to access that page.")
            role = get_user_role(request.user)
            if role == Profile.ROLE_INSTRUCTOR:
                return redirect("instructor_dashboard")
            if role == Profile.ROLE_ADMIN:
                return redirect("admin_dashboard")
            return redirect("student_dashboard")

        return wrapped_view

    return decorator
