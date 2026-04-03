from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Course, Enrollment, Profile


def get_user_role(user):
    profile = getattr(user, "profile", None)
    if profile:
        return profile.role
    if user.is_staff:
        return Profile.ROLE_ADMIN
    return Profile.ROLE_STUDENT


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped_view(request, *args, **kwargs):
            user_role = get_user_role(request.user)
            if user_role in allowed_roles:
                return view_func(request, *args, **kwargs)

            messages.error(request, "You do not have permission to access that page.")
            return redirect_after_login(request.user)

        return _wrapped_view

    return decorator


def get_display_name(user):
    full_name = user.get_full_name().strip()
    return full_name if full_name else user.username


def get_student_courses_seed():
    return [
        {
            "id": 1,
            "name": "Algorithms 101",
            "instructor": "Prof. Pomona Sprout",
            "day": "Tuesday",
            "progress": 35,
            "bg_class": "bg-indigo-50",
            "icon": "ri-code-s-slash-line",
            "icon_color": "text-indigo-600",
            "bar_color": "bg-indigo-400",
            "day_color": "text-amber-500",
        },
        {
            "id": 2,
            "name": "Introduction to Database",
            "instructor": "Prof. Severus Snape",
            "day": "Tuesday",
            "progress": 55,
            "bg_class": "bg-violet-50",
            "icon": "ri-database-2-line",
            "icon_color": "text-violet-600",
            "bar_color": "bg-violet-400",
            "day_color": "text-amber-500",
        },
        {
            "id": 3,
            "name": "Basic Mathematics",
            "instructor": "Prof. Dolores Umbridge",
            "day": "Monday",
            "progress": 80,
            "bg_class": "bg-emerald-50",
            "icon": "ri-pie-chart-line",
            "icon_color": "text-emerald-600",
            "bar_color": "bg-emerald-400",
            "day_color": "text-blue-500",
        },
        {
            "id": 4,
            "name": "Human Computer Interaction",
            "instructor": "Prof. Filius Flitwick",
            "day": "Wednesday",
            "progress": 45,
            "bg_class": "bg-rose-50",
            "icon": "ri-computer-line",
            "icon_color": "text-rose-600",
            "bar_color": "bg-rose-400",
            "day_color": "text-green-500",
        },
    ]


def ensure_seed_courses():
    if Course.objects.exists():
        return

    instructor = User.objects.filter(profile__role=Profile.ROLE_INSTRUCTOR).first()
    if not instructor:
        instructor = User.objects.filter(is_staff=True).first()

    seed_data = [
        ("Algorithms 101", "Computer Science", Course.LEVEL_INTERMEDIATE, 14, 12, 6, 12, 4.8),
        ("Introduction to Database", "Database", Course.LEVEL_BEGINNER, 14, 14, 5, 10, 4.7),
        ("Basic Mathematics", "Mathematics", Course.LEVEL_BEGINNER, 12, 10, 4, 8, 4.5),
        ("Computer Networks", "Networks", Course.LEVEL_ADVANCED, 12, 11, 4, 9, 4.9),
        ("Human Computer Interaction", "Computer Science", Course.LEVEL_INTERMEDIATE, 14, 13, 5, 10, 4.6),
        ("Introduction to Management", "Management", Course.LEVEL_BEGINNER, 10, 9, 3, 6, 4.3),
    ]

    for title, category, level, weeks, lectures, assignments_count, quizzes_count, rating in seed_data:
        Course.objects.create(
            title=title,
            short_description=f"{title} course overview",
            description=f"This is the course page for {title}.",
            category=category,
            level=level,
            duration_weeks=weeks,
            lecture_count=lectures,
            assignment_count=assignments_count,
            quiz_count=quizzes_count,
            rating=rating,
            instructor=instructor,
            is_published=True,
        )


def landing(request):
    return render(request, "landing.html")


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

    return render(request, "login.html")


def logout_page(request):
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
    return HttpResponse("Password reset page coming soon.")


def register_page(request):
    if request.user.is_authenticated:
        return redirect_after_login(request.user)

    if request.method == "POST":
        role = request.POST.get("role", Profile.ROLE_STUDENT).strip().lower()
        first_name = request.POST.get("first_name", "").strip()
        last_name = request.POST.get("last_name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        terms = request.POST.get("terms")

        if not all([first_name, last_name, email, password1, password2]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, "register.html")

        if not terms:
            messages.error(request, "You must accept the terms to continue.")
            return render(request, "register.html")

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, "register.html")

        if len(password1) < 8:
            messages.error(request, "Password must be at least 8 characters long.")
            return render(request, "register.html")

        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, "An account with this email already exists.")
            return render(request, "register.html")

        # Generate unique username from email local-part.
        base_username = email.split("@")[0]
        username = base_username
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            first_name=first_name,
            last_name=last_name,
        )

        if role not in {Profile.ROLE_STUDENT, Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN}:
            role = Profile.ROLE_STUDENT

        Profile.objects.create(user=user, role=role)

        login(request, user)
        messages.success(request, "Account created successfully.")
        return redirect_after_login(user)

    return render(request, "register.html")


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect_after_login(request.user)


@login_required
def course_catalog(request):
    ensure_seed_courses()
    courses = Course.objects.filter(is_published=True).select_related("instructor")
    enrolled_ids = set(
        Enrollment.objects.filter(student=request.user).values_list("course_id", flat=True)
    )
    context = {
        "courses": courses,
        "enrolled_course_ids": enrolled_ids,
    }
    return render(request, "courses/catalog.html", context)


@login_required
def course_detail(request, course_id):
    ensure_seed_courses()
    course = Course.objects.filter(pk=course_id, is_published=True).select_related("instructor").first()
    if not course:
        course = Course.objects.filter(is_published=True).select_related("instructor").first()
        if not course:
            messages.error(request, "No courses are available yet.")
            return redirect("courses")

    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    related_courses = Course.objects.filter(is_published=True).exclude(pk=course.pk)[:2]

    context = {
        "course": course,
        "is_enrolled": enrollment is not None,
        "enrollment": enrollment,
        "related_courses": related_courses,
    }
    return render(request, "courses/detail.html", context)


@login_required
def course_content(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_published=True)
    role = get_user_role(request.user)
    if role == Profile.ROLE_STUDENT and not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "Please enroll in the course first.")
        return redirect("course_detail", course_id=course.id)

    return render(request, "courses/content.html", {"course": course})


@login_required
def course_enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_published=True)

    if request.method != "POST":
        return redirect("course_detail", course_id=course.id)

    if get_user_role(request.user) != Profile.ROLE_STUDENT:
        messages.error(request, "Only students can enroll in courses.")
        return redirect("course_detail", course_id=course.id)

    _, created = Enrollment.objects.get_or_create(student=request.user, course=course)
    if created:
        messages.success(request, f"You are now enrolled in {course.title}.")
    else:
        messages.info(request, f"You are already enrolled in {course.title}.")

    return redirect("course_detail", course_id=course.id)


@login_required
def assignments(request):
    return HttpResponse("Assignments page coming soon.")


@login_required
def grades(request):
    return HttpResponse("Grades page coming soon.")


@login_required
def quiz(request):
    return HttpResponse("Quiz page coming soon.")


@login_required
def settings_page(request):
    return HttpResponse("Settings page coming soon.")


@role_required(Profile.ROLE_STUDENT)
def student_dashboard(request):
    enrollment_qs = Enrollment.objects.filter(student=request.user).select_related("course", "course__instructor")
    courses = [
        {
            "id": e.course.id,
            "name": e.course.title,
            "instructor": get_display_name(e.course.instructor) if e.course.instructor else "TBA",
            "day": "Tuesday",
            "progress": e.progress,
            "bg_class": "bg-indigo-50",
            "icon": "ri-book-open-line",
            "icon_color": "text-indigo-600",
            "bar_color": "bg-indigo-400",
            "day_color": "text-amber-500",
        }
        for e in enrollment_qs
    ]
    if not courses:
        courses = get_student_courses_seed()

    context = {
        "display_name": get_display_name(request.user),
        "courses": courses,
        "student_stats": {
            "course_count": len(courses),
            "pending_assignments": 3,
            "gpa": 3.8,
            "completion": 67,
        },
    }
    return render(request, "dashboard/student.html", context)


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_dashboard(request):
    context = {
        "display_name": get_display_name(request.user),
        "instructor_stats": {
            "courses": 4,
            "students": 284,
            "pending_submissions": 3,
            "completion": 78,
        },
    }
    return render(request, "dashboard/instructor.html", context)


@role_required(Profile.ROLE_ADMIN)
def admin_dashboard(request):
    total_users = User.objects.count()
    instructor_count = Profile.objects.filter(role=Profile.ROLE_INSTRUCTOR).count()
    student_count = Profile.objects.filter(role=Profile.ROLE_STUDENT).count()

    context = {
        "display_name": get_display_name(request.user),
        "admin_stats": {
            "total_users": total_users,
            "students": student_count,
            "instructors": instructor_count,
        },
    }
    return render(request, "dashboard/admin.html", context)


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_create_course(request):
    return render(request, "instructor/create_course.html")


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_submissions(request):
    return render(request, "dashboard/instructor.html")


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_manage_content(request, course_id):
    return render(request, "instructor/manage_content.html", {"course_id": course_id})


@login_required
def profile_page(request):
    return render(request, "profile/profile.html")


@login_required
def announcements(request):
    return render(request, "profile/announcements.html")