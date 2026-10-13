from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from ..models import (
    Announcement, Assignment, Course, CourseDiscussionPost, CourseReview,
    CourseModule, Enrollment, ModuleCompletion, ModuleResource, Profile, Quiz,
    QuizAttempt, QuizQuestion, QuizResponse, Submission,
)
from ..forms import RegistrationForm
from ..permissions import get_user_role, role_required
from ..selectors.course_queries import (
    approved_enrollments_qs, attach_course_rating_metadata,
    get_module_completion_status,
)
from ..utils import build_teacher_id, get_display_name


def landing(request):
    return render(request, "core/landing.html")


def login_page(request):
    if request.user.is_authenticated:
        return redirect_after_login(request.user)

    if request.method == "POST":
        identity = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        username = identity
        if "@" in identity:
            matched = User.objects.filter(email__iexact=identity).first()
            if matched:
                username = matched.username

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect_after_login(user)

        messages.error(request, "Invalid email/username or password.")

    return render(request, "core/login.html")


def logout_page(request):
    if request.method != "POST":
        messages.error(request, "Invalid logout request.")
        return redirect("dashboard")
    logout(request)
    return redirect("landing")


def redirect_after_login(user):
    role = get_user_role(user)
    if role == Profile.ROLE_INSTRUCTOR:
        return redirect("instructor_dashboard")
    if role == Profile.ROLE_ADMIN:
        return redirect("admin_dashboard")
    return redirect("student_dashboard")


def password_reset_page(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if not email:
            messages.error(request, "Please provide your email address.")
            return render(request, "core/password_reset.html")

        # Keep response generic to avoid user enumeration.
        messages.success(
            request,
            "If an account with that email exists, reset instructions will be sent.",
        )
        return render(request, "core/password_reset.html")

    return render(request, "core/password_reset.html")


def register_page(request):
    if request.user.is_authenticated:
        return redirect_after_login(request.user)

    if request.method == "POST":
        form_data = request.POST.copy()
        if form_data.get("role") not in {Profile.ROLE_STUDENT, Profile.ROLE_INSTRUCTOR}:
            form_data["role"] = Profile.ROLE_STUDENT
        form = RegistrationForm(form_data)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect_after_login(user)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    else:
        form = RegistrationForm()

    return render(request, "core/register.html", {"form": form})


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect_after_login(request.user)
