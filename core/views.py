from functools import wraps

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import (
    Announcement,
    Assignment,
    Course,
    CourseDiscussionPost,
    CourseReview,
    CourseModule,
    Enrollment,
    ModuleResource,
    ModuleCompletion,
    Profile,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    QuizResponse,
    Submission,
)


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


def build_teacher_id(user_id):
    return f"TCH-{user_id:05d}"


def approved_enrollments_qs():
    return Enrollment.objects.filter(status=Enrollment.STATUS_APPROVED)


def attach_course_rating_metadata(courses):
    course_list = list(courses)
    if not course_list:
        return course_list

    course_ids = [course.id for course in course_list]
    instructor_ids = [course.instructor_id for course in course_list if course.instructor_id]

    course_stats = {
        row["course_id"]: row
        for row in CourseReview.objects.filter(course_id__in=course_ids)
        .values("course_id")
        .annotate(avg_course=Avg("course_rating"), review_count=Count("id"))
    }
    instructor_stats = {
        row["course__instructor_id"]: row
        for row in CourseReview.objects.filter(course__instructor_id__in=instructor_ids)
        .values("course__instructor_id")
        .annotate(avg_instructor=Avg("instructor_rating"), review_count=Count("id"))
    }

    for course in course_list:
        cstat = course_stats.get(course.id)
        istat = instructor_stats.get(course.instructor_id)
        course.display_course_rating = round(float(cstat["avg_course"]), 1) if cstat and cstat["avg_course"] is not None else float(course.rating or 0)
        course.course_review_count = cstat["review_count"] if cstat else 0
        course.display_instructor_rating = round(float(istat["avg_instructor"]), 1) if istat and istat["avg_instructor"] is not None else 0
        course.instructor_review_count = istat["review_count"] if istat else 0

    return course_list


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
            return render(request, "password_reset.html")

        # Keep response generic to avoid user enumeration.
        messages.success(
            request,
            "If an account with that email exists, reset instructions will be sent.",
        )
        return render(request, "password_reset.html")

    return render(request, "password_reset.html")


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

        # Never allow public registration as admin.
        if role not in {Profile.ROLE_STUDENT, Profile.ROLE_INSTRUCTOR}:
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
    search_query = request.GET.get("q", "").strip()
    published_courses_qs = Course.objects.filter(
        is_published=True,
        instructor__profile__role=Profile.ROLE_INSTRUCTOR,
    )
    courses_qs = published_courses_qs.select_related("instructor")
    if search_query:
        courses_qs = courses_qs.filter(
            Q(title__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(tags__icontains=search_query)
            | Q(instructor__username__icontains=search_query)
            | Q(instructor__first_name__icontains=search_query)
            | Q(instructor__last_name__icontains=search_query)
        )
    courses = attach_course_rating_metadata(courses_qs)

    categories = list(
        published_courses_qs
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    tags = sorted(
        {
            tag.strip()
            for tag_string in published_courses_qs.exclude(tags="").values_list("tags", flat=True)
            for tag in tag_string.split(",")
            if tag.strip()
        },
        key=str.lower,
    )
    enrolled_ids = set(
        approved_enrollments_qs().filter(student=request.user).values_list("course_id", flat=True)
    )
    context = {
        "courses": courses,
        "categories": categories,
        "tags": tags,
        "enrolled_course_ids": enrolled_ids,
        "search_query": search_query,
    }
    return render(request, "courses/catalog.html", context)


@role_required(Profile.ROLE_STUDENT)
def student_course_catalog(request):
    search_query = request.GET.get("q", "").strip()
    published_courses_qs = Course.objects.filter(
        is_published=True,
        instructor__profile__role=Profile.ROLE_INSTRUCTOR,
    )
    courses_qs = published_courses_qs.select_related("instructor")

    if search_query:
        courses_qs = courses_qs.filter(
            Q(title__icontains=search_query)
            | Q(category__icontains=search_query)
            | Q(tags__icontains=search_query)
            | Q(instructor__username__icontains=search_query)
            | Q(instructor__first_name__icontains=search_query)
            | Q(instructor__last_name__icontains=search_query)
        )
    courses = attach_course_rating_metadata(courses_qs)

    categories = list(
        published_courses_qs
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
    tags = sorted(
        {
            tag.strip()
            for tag_string in published_courses_qs.exclude(tags="").values_list("tags", flat=True)
            for tag in tag_string.split(",")
            if tag.strip()
        },
        key=str.lower,
    )
    enrolled_ids = set(
        approved_enrollments_qs().filter(student=request.user).values_list("course_id", flat=True)
    )
    context = {
        "courses": courses,
        "categories": categories,
        "tags": tags,
        "enrolled_course_ids": enrolled_ids,
        "search_query": search_query,
        "is_dedicated_student_catalog": True,
    }
    return render(request, "courses/catalog.html", context)


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_my_courses(request):
    role = get_user_role(request.user)
    if role == Profile.ROLE_ADMIN:
        instructor_courses = Course.objects.filter(is_published=True)
    else:
        instructor_courses = Course.objects.filter(instructor=request.user, is_published=True)

    if request.method == "POST":
        action = request.POST.get("action", "remove_enrollment").strip()
        enrollment_id = request.POST.get("enrollment_id", "").strip()
        enrollment = (
            Enrollment.objects.filter(pk=enrollment_id, course__in=instructor_courses)
            .select_related("student", "course")
            .first()
        )
        if not enrollment:
            messages.error(request, "Enrollment record was not found.")
            return redirect("instructor_my_courses")

        student_name = get_display_name(enrollment.student)
        course_title = enrollment.course.title

        if action == "approve_enrollment":
            if enrollment.status == Enrollment.STATUS_APPROVED:
                messages.info(request, f"{student_name} is already approved for {course_title}.")
                return redirect("instructor_my_courses")

            if enrollment.course.is_at_capacity():
                messages.error(request, f"Cannot approve {student_name}. {course_title} is already at max capacity.")
                return redirect("instructor_my_courses")

            enrollment.status = Enrollment.STATUS_APPROVED
            enrollment.approved_at = timezone.now()
            enrollment.save(update_fields=["status", "approved_at"])
            messages.success(request, f"Approved {student_name} for {course_title}.")
            return redirect("instructor_my_courses")

        if action == "reject_enrollment":
            enrollment.delete()
            messages.success(request, f"Rejected enrollment request of {student_name} for {course_title}.")
            return redirect("instructor_my_courses")

        enrollment.delete()
        messages.success(request, f"Removed {student_name} from {course_title}.")
        return redirect("instructor_my_courses")

    course_list = list(instructor_courses.select_related("instructor").order_by("title"))
    if not course_list:
        return render(
            request,
            "instructor/my_courses.html",
            {
                "course_rows": [],
                "display_name": get_display_name(request.user),
            },
        )

    course_ids = [course.id for course in course_list]
    assignment_total_by_course = dict(
        Assignment.objects.filter(
            course_id__in=course_ids,
            is_published=True,
            archived_at__isnull=True,
        )
        .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=timezone.now()))
        .values("course_id")
        .annotate(total=Count("id"))
        .values_list("course_id", "total")
    )
    quiz_total_by_course = dict(
        Quiz.objects.filter(course_id__in=course_ids, is_published=True)
        .values("course_id")
        .annotate(total=Count("id"))
        .values_list("course_id", "total")
    )

    submission_stats = {
        (row["assignment__course_id"], row["student_id"]): {
            "submitted": row["submitted_count"],
            "graded": row["graded_count"],
        }
        for row in Submission.objects.filter(assignment__course_id__in=course_ids)
        .values("assignment__course_id", "student_id")
        .annotate(
            submitted_count=Count("id"),
            graded_count=Count("id", filter=Q(status=Submission.STATUS_GRADED)),
        )
    }

    quiz_attempt_stats = {
        (row["quiz__course_id"], row["student_id"]): row["completed_count"]
        for row in QuizAttempt.objects.filter(
            quiz__course_id__in=course_ids,
            submitted_at__isnull=False,
        )
        .values("quiz__course_id", "student_id")
        .annotate(completed_count=Count("id"))
    }

    enrollment_rows = list(
        approved_enrollments_qs().filter(course_id__in=course_ids)
        .select_related("student", "course")
        .order_by("course__title", "student__first_name", "student__username")
    )
    pending_rows = list(
        Enrollment.objects.filter(
            course_id__in=course_ids,
            status=Enrollment.STATUS_PENDING,
        )
        .select_related("student", "course")
        .order_by("course__title", "enrolled_at")
    )
    students_by_course = {course_id: [] for course_id in course_ids}
    pending_by_course = {course_id: [] for course_id in course_ids}
    for enrollment in enrollment_rows:
        stats_key = (enrollment.course_id, enrollment.student_id)
        submission_info = submission_stats.get(stats_key, {"submitted": 0, "graded": 0})
        students_by_course[enrollment.course_id].append(
            {
                "enrollment_id": enrollment.id,
                "student": enrollment.student,
                "module_progress": enrollment.progress,
                "submitted_assignments": submission_info["submitted"],
                "graded_assignments": submission_info["graded"],
                "completed_quizzes": quiz_attempt_stats.get(stats_key, 0),
            }
        )
    for enrollment in pending_rows:
        pending_by_course[enrollment.course_id].append(
            {
                "enrollment_id": enrollment.id,
                "student": enrollment.student,
                "requested_at": enrollment.enrolled_at,
            }
        )

    course_rows = []
    for course in course_list:
        total_assignments = assignment_total_by_course.get(course.id, 0)
        total_quizzes = quiz_total_by_course.get(course.id, 0)
        students = students_by_course.get(course.id, [])
        course_rows.append(
            {
                "course": course,
                "student_count": len(students),
                "pending_count": len(pending_by_course.get(course.id, [])),
                "total_assignments": total_assignments,
                "total_quizzes": total_quizzes,
                "students": students,
                "pending_requests": pending_by_course.get(course.id, []),
            }
        )

    context = {
        "display_name": get_display_name(request.user),
        "course_rows": course_rows,
    }
    return render(request, "instructor/my_courses.html", context)


@login_required
def course_detail(request, course_id):
    course = get_object_or_404(
        Course.objects.select_related("instructor"),
        pk=course_id,
        is_published=True,
        instructor__profile__role=Profile.ROLE_INSTRUCTOR,
    )

    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    is_enrolled = bool(enrollment and enrollment.status == Enrollment.STATUS_APPROVED)
    is_pending_approval = bool(enrollment and enrollment.status == Enrollment.STATUS_PENDING)
    related_courses = Course.objects.filter(
        is_published=True,
        instructor__profile__role=Profile.ROLE_INSTRUCTOR,
    ).exclude(pk=course.pk)[:2]
    modules = course.modules.filter(is_published=True).prefetch_related("resources")
    role = get_user_role(request.user)
    course = attach_course_rating_metadata([course])[0]

    recent_reviews = CourseReview.objects.filter(course=course).select_related("student")[:4]
    my_review = None
    if role == Profile.ROLE_STUDENT and is_enrolled:
        my_review = CourseReview.objects.filter(course=course, student=request.user).first()
    context = {
        "course": course,
        "is_enrolled": is_enrolled,
        "is_pending_approval": is_pending_approval,
        "enrollment": enrollment,
        "related_courses": related_courses,
        "modules": modules,
        "module_count": modules.count(),
        "resource_count": ModuleResource.objects.filter(module__course=course, is_published=True).count(),
        "is_student": role == Profile.ROLE_STUDENT,
        "is_instructor": role == Profile.ROLE_INSTRUCTOR,
        "is_admin": role == Profile.ROLE_ADMIN,
        "recent_reviews": recent_reviews,
        "my_review": my_review,
    }
    return render(request, "courses/detail.html", context)


@role_required(Profile.ROLE_STUDENT)
def course_submit_review(request, course_id):
    if request.method != "POST":
        return redirect("course_detail", course_id=course_id)

    course = get_object_or_404(Course, pk=course_id, is_published=True)
    if not approved_enrollments_qs().filter(student=request.user, course=course).exists():
        messages.error(request, "You can only review courses you are enrolled in.")
        return redirect("course_detail", course_id=course.id)

    course_rating_raw = request.POST.get("course_rating", "").strip()
    instructor_rating_raw = request.POST.get("instructor_rating", "").strip()
    comment = request.POST.get("comment", "").strip()

    try:
        course_rating = int(course_rating_raw)
        instructor_rating = int(instructor_rating_raw)
    except ValueError:
        messages.error(request, "Please select both course and instructor ratings.")
        return redirect("course_detail", course_id=course.id)

    if not (1 <= course_rating <= 5 and 1 <= instructor_rating <= 5):
        messages.error(request, "Ratings must be between 1 and 5 stars.")
        return redirect("course_detail", course_id=course.id)

    CourseReview.objects.update_or_create(
        course=course,
        student=request.user,
        defaults={
            "course_rating": course_rating,
            "instructor_rating": instructor_rating,
            "comment": comment,
        },
    )

    aggregate = CourseReview.objects.filter(course=course).aggregate(avg_course=Avg("course_rating"))
    course.rating = round(float(aggregate["avg_course"] or 0), 1)
    course.save(update_fields=["rating", "updated_at"])

    messages.success(request, "Thanks! Your review has been saved.")
    return redirect("course_detail", course_id=course.id)


@login_required
def course_content(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_published=True)
    role = get_user_role(request.user)
    enrollment = approved_enrollments_qs().filter(student=request.user, course=course).first()
    if role == Profile.ROLE_STUDENT and not enrollment:
        messages.error(request, "Please enroll in the course first.")
        return redirect("course_detail", course_id=course.id)

    if request.method == "POST" and role == Profile.ROLE_STUDENT and enrollment:
        action = request.POST.get("action", "").strip().lower()
        module_id = request.POST.get("module_id", "").strip()
        module = course.modules.filter(pk=module_id, is_published=True).first()
        if not module:
            messages.error(request, "Selected module was not found.")
            return redirect("course_content", course_id=course.id)

        if action == "complete_module":
            ModuleCompletion.objects.get_or_create(enrollment=enrollment, module=module)
            messages.success(request, f"Marked '{module.title}' as completed.")
        elif action == "undo_module":
            ModuleCompletion.objects.filter(enrollment=enrollment, module=module).delete()
            messages.info(request, f"Marked '{module.title}' as not completed.")

        total_modules = course.modules.filter(is_published=True).count()
        completed_modules = ModuleCompletion.objects.filter(
            enrollment=enrollment,
            module__course=course,
            module__is_published=True,
        ).count()
        enrollment.progress = round((completed_modules / total_modules) * 100) if total_modules else 0
        enrollment.save(update_fields=["progress"])
        return redirect("course_content", course_id=course.id)

    modules = list(
        course.modules.filter(is_published=True)
        .prefetch_related("resources")
        .order_by("order", "id")
    )
    total_resources = ModuleResource.objects.filter(module__course=course, is_published=True).count()

    completed_module_ids = set()
    course_progress = enrollment.progress if enrollment else 0
    if enrollment:
        completed_module_ids = set(
            ModuleCompletion.objects.filter(
                enrollment=enrollment,
                module__course=course,
                module__is_published=True,
            ).values_list("module_id", flat=True)
        )
        total_modules = len(modules)
        if total_modules:
            # Keep stored progress aligned in case modules were added/removed.
            computed_progress = round((len(completed_module_ids) / total_modules) * 100)
            if computed_progress != enrollment.progress:
                enrollment.progress = computed_progress
                enrollment.save(update_fields=["progress"])
            course_progress = computed_progress

    selected_resource = None
    selected_module_id = request.GET.get("module", "").strip()
    selected_resource_id = request.GET.get("resource", "").strip()
    for module in modules:
        resources = [r for r in module.resources.all() if r.is_published]
        if not resources:
            continue
        if selected_module_id and selected_resource_id and str(module.id) == selected_module_id:
            selected_resource = next((r for r in resources if str(r.id) == selected_resource_id), None)
            if selected_resource:
                break

    if not selected_resource:
        for module in modules:
            resources = [r for r in module.resources.all() if r.is_published]
            first_video = next((r for r in resources if r.resource_type == ModuleResource.TYPE_VIDEO and r.video_file), None)
            if first_video:
                selected_resource = first_video
                break

    if not selected_resource:
        for module in modules:
            resources = [r for r in module.resources.all() if r.is_published]
            if resources:
                selected_resource = resources[0]
                break

    return render(
        request,
        "courses/content.html",
        {
            "course": course,
            "modules": modules,
            "total_resources": total_resources,
            "video_resources": ModuleResource.objects.filter(
                module__course=course,
                is_published=True,
                resource_type=ModuleResource.TYPE_VIDEO,
            ).count(),
            "selected_resource": selected_resource,
            "completed_module_ids": completed_module_ids,
            "course_progress": course_progress,
        },
    )


@login_required
def course_discussion(request, course_id):
    course = get_object_or_404(
        Course.objects.select_related("instructor"),
        pk=course_id,
        is_published=True,
    )
    role = get_user_role(request.user)
    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    is_student_enrolled = bool(enrollment and enrollment.status == Enrollment.STATUS_APPROVED)
    is_course_staff = role == Profile.ROLE_ADMIN or course.instructor_id == request.user.id

    if role == Profile.ROLE_STUDENT and not is_student_enrolled:
        messages.error(request, "You can join discussion only after enrollment approval.")
        return redirect("course_detail", course_id=course.id)

    if not course.allow_discussions and not is_course_staff:
        messages.error(request, "Discussion is disabled for this course.")
        return redirect("course_detail", course_id=course.id)

    can_post = is_course_staff or is_student_enrolled

    if request.method == "POST":
        if not can_post:
            messages.error(request, "You are not allowed to post in this discussion.")
            return redirect("course_discussion", course_id=course.id)

        message = request.POST.get("message", "").strip()
        if not message:
            messages.error(request, "Message cannot be empty.")
            return redirect("course_discussion", course_id=course.id)

        CourseDiscussionPost.objects.create(
            course=course,
            author=request.user,
            message=message[:2000],
        )
        messages.success(request, "Message posted.")
        return redirect("course_discussion", course_id=course.id)

    posts = CourseDiscussionPost.objects.filter(course=course).select_related("author")
    return render(
        request,
        "courses/discussion.html",
        {
            "course": course,
            "posts": posts,
            "can_post": can_post,
            "is_student": role == Profile.ROLE_STUDENT,
            "is_instructor": role == Profile.ROLE_INSTRUCTOR,
            "is_admin": role == Profile.ROLE_ADMIN,
        },
    )


@login_required
def course_enroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_published=True)

    if request.method != "POST":
        return redirect("course_detail", course_id=course.id)

    if get_user_role(request.user) != Profile.ROLE_STUDENT:
        messages.error(request, "Only students can enroll in courses.")
        return redirect("course_detail", course_id=course.id)

    existing_enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if existing_enrollment:
        if existing_enrollment.status == Enrollment.STATUS_APPROVED:
            messages.info(request, f"You are already enrolled in {course.title}.")
        else:
            messages.info(request, f"Your enrollment request for {course.title} is still pending approval.")
        return redirect("course_detail", course_id=course.id)

    if course.is_at_capacity():
        messages.error(request, f"{course.title} has reached maximum student capacity.")
        return redirect("course_detail", course_id=course.id)

    if course.enrollment_type == Course.ENROLLMENT_APPROVAL:
        Enrollment.objects.create(
            student=request.user,
            course=course,
            status=Enrollment.STATUS_PENDING,
        )
        messages.success(request, f"Enrollment request sent for {course.title}. Waiting for instructor approval.")
    else:
        Enrollment.objects.create(
            student=request.user,
            course=course,
            status=Enrollment.STATUS_APPROVED,
            approved_at=timezone.now(),
        )
        messages.success(request, f"You are now enrolled in {course.title}.")

    return redirect("course_detail", course_id=course.id)


@login_required
def course_unenroll(request, course_id):
    course = get_object_or_404(Course, pk=course_id, is_published=True)

    if request.method != "POST":
        return redirect("course_detail", course_id=course.id)

    if get_user_role(request.user) != Profile.ROLE_STUDENT:
        messages.error(request, "Only students can drop courses.")
        return redirect("course_detail", course_id=course.id)

    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if not enrollment:
        messages.info(request, f"You are not enrolled in {course.title}.")
        return redirect("course_detail", course_id=course.id)

    was_pending = enrollment.status == Enrollment.STATUS_PENDING
    enrollment.delete()
    if was_pending:
        messages.success(request, f"Your pending enrollment request for {course.title} was canceled.")
    else:
        messages.success(request, f"You have dropped {course.title}.")

    return redirect("course_detail", course_id=course.id)


@login_required
def assignments(request):
    role = get_user_role(request.user)
    now = timezone.now()
    student_course_ids = Enrollment.objects.none().values_list("course_id", flat=True)
    if role == Profile.ROLE_STUDENT:
        student_course_ids = approved_enrollments_qs().filter(student=request.user).values_list("course_id", flat=True)
        assignment_qs = Assignment.objects.filter(
            is_published=True,
            archived_at__isnull=True,
            course_id__in=student_course_ids,
        ).filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now))
    elif role in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN}:
        assignment_qs = Assignment.objects.filter(
            archived_at__isnull=True,
        ).filter(Q(created_by=request.user) | Q(course__instructor=request.user))
    else:
        assignment_qs = Assignment.objects.none()

    assignment_qs = assignment_qs.select_related("course").order_by("due_date", "title")

    if request.method == "POST":
        if role != Profile.ROLE_STUDENT:
            messages.error(request, "Only students can submit assignments.")
            return redirect("assignments")

        assignment_id = request.POST.get("assignment_id")
        assignment_title = request.POST.get("assignment_title", "").strip()
        upload = request.FILES.get("submission")
        comment = request.POST.get("comment", "").strip()

        assignment = None
        if assignment_id:
            assignment = Assignment.objects.filter(
                pk=assignment_id,
                is_published=True,
                archived_at__isnull=True,
            ).filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now)).first()
        elif assignment_title:
            assignment = Assignment.objects.filter(
                title__iexact=assignment_title,
                is_published=True,
                archived_at__isnull=True,
                course_id__in=student_course_ids,
            ).filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now)).first()

        if not assignment:
            messages.error(request, "Selected assignment does not exist.")
            return redirect("assignments")

        if assignment.course_id not in set(student_course_ids):
            messages.error(request, "You can only submit assignments for your enrolled courses.")
            return redirect("assignments")

        if not upload:
            messages.error(request, "Please choose a file before submitting.")
            return redirect("assignments")

        submission, created = Submission.objects.get_or_create(
            assignment=assignment,
            student=request.user,
            defaults={"file": upload, "comment": comment},
        )
        if not created:
            submission.file = upload
            submission.comment = comment
            submission.status = Submission.STATUS_SUBMITTED
            submission.save(update_fields=["file", "comment", "status", "updated_at"])

        messages.success(request, f"Submitted {assignment.title} successfully.")

        return redirect("assignments")

    assignment_rows = []
    if role == Profile.ROLE_STUDENT:
        submission_map = {
            submission.assignment_id: submission
            for submission in Submission.objects.filter(
                student=request.user,
                assignment__in=assignment_qs,
            ).select_related("assignment")
        }
        for assignment in assignment_qs:
            assignment_rows.append(
                {
                    "assignment": assignment,
                    "submission": submission_map.get(assignment.id),
                }
            )
    else:
        assignment_rows = [{"assignment": assignment, "submission": None} for assignment in assignment_qs]

    return render(
        request,
        "assessment/assignment.html",
        {
            "assignments": assignment_qs,
            "assignment_rows": assignment_rows,
            "is_student": role == Profile.ROLE_STUDENT,
            "is_instructor": role == Profile.ROLE_INSTRUCTOR,
            "is_admin": role == Profile.ROLE_ADMIN,
        },
    )


@login_required
def grades(request):
    submissions = Submission.objects.filter(student=request.user).select_related("assignment", "assignment__course")
    quiz_attempts = QuizAttempt.objects.filter(student=request.user).select_related("quiz", "quiz__course")

    graded_submissions = submissions.exclude(score__isnull=True)
    avg_assignment = round(
        sum(float(s.score) for s in graded_submissions) / graded_submissions.count(), 2
    ) if graded_submissions.exists() else 0

    avg_quiz = round(
        sum(float(a.score) for a in quiz_attempts) / quiz_attempts.count(), 2
    ) if quiz_attempts.exists() else 0

    return render(
        request,
        "assessment/grades.html",
        {
            "grade_data": {
                "assignment_average": avg_assignment,
                "quiz_average": avg_quiz,
                "graded_assignments": graded_submissions.count(),
                "quiz_attempts": quiz_attempts.count(),
            },
            "submissions": submissions,
            "quiz_attempts_list": quiz_attempts,
        },
    )


@login_required
def quiz(request):
    role = get_user_role(request.user)

    instructor_courses = Course.objects.none()
    if role == Profile.ROLE_INSTRUCTOR:
        instructor_courses = Course.objects.filter(instructor=request.user, is_published=True)
    elif role == Profile.ROLE_ADMIN:
        instructor_courses = Course.objects.filter(is_published=True)

    if request.method == "POST":
        if role not in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN}:
            messages.error(request, "Only instructors can create quizzes.")
            return redirect("quiz")

        title = request.POST.get("title", "").strip()
        course_id = request.POST.get("course_id", "").strip()
        total_marks_raw = request.POST.get("total_marks", "100").strip()
        time_limit_raw = request.POST.get("time_limit_minutes", "30").strip()

        if not title:
            messages.error(request, "Quiz title is required.")
            return redirect("quiz")

        selected_course = instructor_courses.filter(pk=course_id).first()
        if not selected_course:
            messages.error(request, "Please choose a valid course.")
            return redirect("quiz")

        try:
            total_marks = int(total_marks_raw)
        except ValueError:
            total_marks = 100

        try:
            time_limit_minutes = int(time_limit_raw)
        except ValueError:
            time_limit_minutes = 30

        quiz_obj = Quiz.objects.create(
            course=selected_course,
            title=title,
            total_marks=max(1, total_marks),
            time_limit_minutes=max(1, time_limit_minutes),
            created_by=request.user,
            is_published=True,
        )
        messages.success(request, f"Quiz '{quiz_obj.title}' created successfully.")
        return redirect("quiz")

    if role == Profile.ROLE_STUDENT:
        student_course_ids = approved_enrollments_qs().filter(student=request.user).values_list("course_id", flat=True)
        quizzes = Quiz.objects.filter(is_published=True, course_id__in=student_course_ids)
    elif role in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN}:
        quizzes = Quiz.objects.filter(Q(created_by=request.user) | Q(course__instructor=request.user))
    else:
        quizzes = Quiz.objects.none()

    quizzes = quizzes.select_related("course").prefetch_related("questions", "attempts")

    course_ids = list({q.course_id for q in quizzes})
    quiz_ids = [q.id for q in quizzes]
    enrolled_by_course = {
        row["course_id"]: row["student_total"]
        for row in approved_enrollments_qs().filter(course_id__in=course_ids)
        .values("course_id")
        .annotate(student_total=Count("student", distinct=True))
    }
    submitted_attempts_qs = QuizAttempt.objects.filter(
        quiz_id__in=quiz_ids,
        submitted_at__isnull=False,
    ).select_related("quiz")

    submitted_count_by_quiz = {}
    score_pct_sum_by_quiz = {}
    submitted_student_ids_by_quiz = {}
    for attempt in submitted_attempts_qs:
        qid = attempt.quiz_id
        submitted_count_by_quiz[qid] = submitted_count_by_quiz.get(qid, 0) + 1
        submitted_student_ids_by_quiz.setdefault(qid, set()).add(attempt.student_id)
        total_marks = float(attempt.quiz.total_marks or 0)
        if total_marks > 0:
            pct = (float(attempt.score) / total_marks) * 100
            score_pct_sum_by_quiz[qid] = score_pct_sum_by_quiz.get(qid, 0.0) + pct

    course_students_map = {}
    course_student_ids_map = {}
    if role in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN} and course_ids:
        for enrollment in approved_enrollments_qs().filter(course_id__in=course_ids).select_related("student"):
            student_name = get_display_name(enrollment.student)
            course_students_map.setdefault(enrollment.course_id, []).append(
                {
                    "id": enrollment.student_id,
                    "name": student_name,
                }
            )
            course_student_ids_map.setdefault(enrollment.course_id, set()).add(enrollment.student_id)

    attempts_by_quiz = {}
    if role == Profile.ROLE_STUDENT:
        for attempt in QuizAttempt.objects.filter(student=request.user, quiz__in=quizzes):
            attempts_by_quiz[attempt.quiz_id] = attempt

    quiz_cards = []
    total_attempts = 0
    total_pct = 0.0
    scored_attempt_count = 0

    for quiz_obj in quizzes:
        question_count = quiz_obj.questions.count()
        total_marks = quiz_obj.total_marks or max(question_count, 1)
        attempt_count = submitted_count_by_quiz.get(quiz_obj.id, 0)
        total_attempts += attempt_count
        eligible_students = enrolled_by_course.get(quiz_obj.course_id, 0)
        avg_score_pct = round(score_pct_sum_by_quiz.get(quiz_obj.id, 0.0) / attempt_count) if attempt_count else 0
        participation_pct = round((attempt_count / eligible_students) * 100) if eligible_students else 0

        if role in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN} and attempt_count:
            total_pct += score_pct_sum_by_quiz.get(quiz_obj.id, 0.0)
            scored_attempt_count += attempt_count

        card = {
            "id": quiz_obj.id,
            "title": quiz_obj.title,
            "course_id": quiz_obj.course_id,
            "course_title": quiz_obj.course.title,
            "question_count": question_count,
            "time_limit_minutes": quiz_obj.time_limit_minutes,
            "total_marks": total_marks,
            "attempt_count": attempt_count,
            "is_completed": False,
            "score_label": "",
            "score_pct": 0,
            "eligible_students": eligible_students,
            "avg_score_pct": avg_score_pct,
            "participation_pct": participation_pct,
            "attempted_students": [],
            "not_attempted_students": [],
        }

        if role in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN}:
            attempted_ids = submitted_student_ids_by_quiz.get(quiz_obj.id, set())
            all_students = course_students_map.get(quiz_obj.course_id, [])
            card["attempted_students"] = [
                student for student in all_students if student["id"] in attempted_ids
            ]
            card["not_attempted_students"] = [
                student for student in all_students if student["id"] not in attempted_ids
            ]

        if role == Profile.ROLE_STUDENT:
            attempt = attempts_by_quiz.get(quiz_obj.id)
            if attempt and attempt.submitted_at:
                score = float(attempt.score)
                score_pct = max(0, min(100, round((score / total_marks) * 100))) if total_marks else 0
                card["is_completed"] = True
                card["score_label"] = f"{score:g}/{total_marks:g}"
                card["score_pct"] = score_pct
                total_pct += score_pct
                scored_attempt_count += 1

        quiz_cards.append(card)

    if role == Profile.ROLE_STUDENT:
        completed_count = len([c for c in quiz_cards if c["is_completed"]])
        stats = {
            "total": len(quiz_cards),
            "completed": completed_count,
            "pending": max(0, len(quiz_cards) - completed_count),
            "avg_pct": round(total_pct / scored_attempt_count) if scored_attempt_count else 0,
        }
    else:
        students_attempted = submitted_attempts_qs.values("student_id").distinct().count()
        total_students_in_courses = approved_enrollments_qs().filter(course_id__in=course_ids).values("student_id").distinct().count()
        stats = {
            "total": len(quiz_cards),
            "completed": students_attempted,
            "pending": max(0, total_students_in_courses - students_attempted),
            "avg_pct": round(total_pct / scored_attempt_count) if scored_attempt_count else 0,
            "total_attempts": total_attempts,
            "total_students": total_students_in_courses,
            "participation_pct": round((students_attempted / total_students_in_courses) * 100) if total_students_in_courses else 0,
        }

    return render(
        request,
        "assessment/quiz.html",
        {
            "quiz_cards": quiz_cards,
            "quiz_stats": stats,
            "is_student": role == Profile.ROLE_STUDENT,
            "is_instructor": role == Profile.ROLE_INSTRUCTOR,
            "is_admin": role == Profile.ROLE_ADMIN,
            "instructor_courses": instructor_courses,
        },
    )


@role_required(Profile.ROLE_STUDENT)
def quiz_take(request, quiz_id):
    quiz_obj = get_object_or_404(
        Quiz.objects.select_related("course").prefetch_related("questions"),
        pk=quiz_id,
        is_published=True,
    )

    if not approved_enrollments_qs().filter(student=request.user, course=quiz_obj.course).exists():
        messages.error(request, "You can only take quizzes for enrolled courses.")
        return redirect("quiz")

    questions = list(quiz_obj.questions.order_by("order", "id"))
    if not questions:
        messages.error(request, "This quiz has no questions yet.")
        return redirect("quiz")

    attempt, _ = QuizAttempt.objects.get_or_create(quiz=quiz_obj, student=request.user)

    if request.method == "POST":
        if attempt.submitted_at:
            messages.info(request, "You have already submitted this quiz.")
            return redirect("quiz_take", quiz_id=quiz_obj.id)

        total_score = 0.0
        responses_by_question_id = {}

        for question in questions:
            raw_answer = request.POST.get(f"answer_{question.id}", "").strip()
            correct = False
            awarded = 0.0

            if raw_answer and question.correct_answer:
                correct = raw_answer.lower() == question.correct_answer.strip().lower()

            if correct:
                awarded = float(question.marks)
                total_score += awarded

            response, _ = QuizResponse.objects.update_or_create(
                attempt=attempt,
                question=question,
                defaults={
                    "answer_text": raw_answer,
                    "is_correct": correct,
                    "awarded_marks": awarded,
                },
            )
            responses_by_question_id[question.id] = response

        attempt.score = total_score
        attempt.submitted_at = timezone.now()
        attempt.save(update_fields=["score", "submitted_at"])
        messages.success(request, f"Quiz submitted. Your score is {total_score:g}/{quiz_obj.total_marks:g}.")
        return redirect("quiz_take", quiz_id=quiz_obj.id)

    existing_responses = {
        response.question_id: response
        for response in attempt.responses.select_related("question")
    }
    question_rows = [
        {
            "question": question,
            "response": existing_responses.get(question.id),
        }
        for question in questions
    ]

    return render(
        request,
        "assessment/quiz_take.html",
        {
            "quiz_obj": quiz_obj,
            "questions": questions,
            "question_rows": question_rows,
            "attempt": attempt,
            "is_submitted": attempt.submitted_at is not None,
        },
    )


@login_required
def settings_page(request):
    return render(request, "settings.html")


@role_required(Profile.ROLE_STUDENT)
def student_dashboard(request):
    now = timezone.now()
    enrollment_qs = list(approved_enrollments_qs().filter(student=request.user).select_related("course", "course__instructor"))
    course_ids = [e.course_id for e in enrollment_qs]
    enrolled_course_ids = set(course_ids)

    published_assignments = Assignment.objects.filter(
        is_published=True,
        archived_at__isnull=True,
        course_id__in=course_ids,
    ).filter(Q(publish_at__isnull=True) | Q(publish_at__lte=now))
    assignment_totals = {
        row["course_id"]: row["total"]
        for row in published_assignments.values("course_id").annotate(total=Count("id"))
    }

    student_submissions = list(
        Submission.objects.filter(
            student=request.user,
            assignment__course_id__in=course_ids,
        ).select_related("assignment")
    )
    submitted_assignments_by_course = {}
    assignment_percentages_by_course = {}
    for sub in student_submissions:
        cid = sub.assignment.course_id
        submitted_assignments_by_course[cid] = submitted_assignments_by_course.get(cid, 0) + 1
        if sub.score is not None and sub.assignment.max_score:
            pct = (float(sub.score) / float(sub.assignment.max_score)) * 100
            assignment_percentages_by_course.setdefault(cid, []).append(pct)

    published_quizzes = Quiz.objects.filter(is_published=True, course_id__in=course_ids)
    quiz_totals = {
        row["course_id"]: row["total"]
        for row in published_quizzes.values("course_id").annotate(total=Count("id"))
    }

    submitted_quiz_attempts = list(
        QuizAttempt.objects.filter(
            student=request.user,
            quiz__course_id__in=course_ids,
            submitted_at__isnull=False,
        ).select_related("quiz")
    )
    completed_quizzes_by_course = {}
    quiz_percentages_by_course = {}
    for attempt in submitted_quiz_attempts:
        cid = attempt.quiz.course_id
        completed_quizzes_by_course[cid] = completed_quizzes_by_course.get(cid, 0) + 1
        total_marks = float(attempt.quiz.total_marks or 0)
        if total_marks > 0:
            pct = (float(attempt.score) / total_marks) * 100
            quiz_percentages_by_course.setdefault(cid, []).append(pct)

    courses = []
    total_pending_assignments = 0
    total_pending_quizzes = 0
    all_assignment_pcts = []
    all_quiz_pcts = []

    for enrollment in enrollment_qs:
        cid = enrollment.course_id
        assignment_total = assignment_totals.get(cid, 0)
        submitted_assignment_count = submitted_assignments_by_course.get(cid, 0)
        assignment_pending = max(0, assignment_total - submitted_assignment_count)

        quiz_total = quiz_totals.get(cid, 0)
        completed_quiz_count = completed_quizzes_by_course.get(cid, 0)
        quiz_pending = max(0, quiz_total - completed_quiz_count)

        assignment_pcts = assignment_percentages_by_course.get(cid, [])
        quiz_pcts = quiz_percentages_by_course.get(cid, [])
        assignment_avg = round(sum(assignment_pcts) / len(assignment_pcts), 1) if assignment_pcts else 0
        quiz_avg = round(sum(quiz_pcts) / len(quiz_pcts), 1) if quiz_pcts else 0

        total_pending_assignments += assignment_pending
        total_pending_quizzes += quiz_pending
        all_assignment_pcts.extend(assignment_pcts)
        all_quiz_pcts.extend(quiz_pcts)

        courses.append(
            {
                "id": enrollment.course.id,
                "name": enrollment.course.title,
                "instructor": get_display_name(enrollment.course.instructor) if enrollment.course.instructor else "TBA",
                "progress": enrollment.progress,
                "assignment_total": assignment_total,
                "assignment_submitted": submitted_assignment_count,
                "assignment_pending": assignment_pending,
                "assignment_avg": assignment_avg,
                "quiz_total": quiz_total,
                "quiz_completed": completed_quiz_count,
                "quiz_pending": quiz_pending,
                "quiz_avg": quiz_avg,
            }
        )

    overall_assignment_avg = round(sum(all_assignment_pcts) / len(all_assignment_pcts), 1) if all_assignment_pcts else 0
    overall_quiz_avg = round(sum(all_quiz_pcts) / len(all_quiz_pcts), 1) if all_quiz_pcts else 0

    popular_course_ids = list(
        Course.objects.filter(is_published=True, instructor__profile__role=Profile.ROLE_INSTRUCTOR)
        .annotate(popularity=Count("enrollments"))
        .order_by("-popularity", "-rating", "title")
        .values_list("id", flat=True)[:6]
    )
    popular_course_index = {cid: idx for idx, cid in enumerate(popular_course_ids)}
    popular_courses = []
    if popular_course_ids:
        for course in attach_course_rating_metadata(
            Course.objects.filter(id__in=popular_course_ids).select_related("instructor")
        ):
            popular_courses.append(
                {
                    "id": course.id,
                    "title": course.title,
                    "instructor": get_display_name(course.instructor) if course.instructor else "TBA",
                    "enrollment_count": course.enrollments.count(),
                    "course_rating": course.display_course_rating,
                    "instructor_rating": course.display_instructor_rating,
                    "is_enrolled": course.id in enrolled_course_ids,
                }
            )
        popular_courses.sort(key=lambda c: popular_course_index.get(c["id"], 99))

    top_instructor_rows = (
        User.objects.filter(
            profile__role=Profile.ROLE_INSTRUCTOR,
            courses_taught__is_published=True,
        )
        .annotate(
            published_courses=Count("courses_taught", filter=Q(courses_taught__is_published=True), distinct=True),
            student_count=Count("courses_taught__enrollments", distinct=True),
            avg_instructor_rating=Avg("courses_taught__reviews__instructor_rating"),
            review_count=Count("courses_taught__reviews", distinct=True),
        )
        .order_by("-student_count", "-avg_instructor_rating", "username")[:5]
    )

    top_instructors = [
        {
            "id": instructor.id,
            "name": get_display_name(instructor),
            "courses": instructor.published_courses or 0,
            "students": instructor.student_count or 0,
            "rating": round(float(instructor.avg_instructor_rating), 1) if instructor.avg_instructor_rating is not None else 0,
            "review_count": instructor.review_count or 0,
        }
        for instructor in top_instructor_rows
    ]

    context = {
        "display_name": get_display_name(request.user),
        "courses": courses,
        "student_stats": {
            "course_count": len(courses),
            "pending_assignments": total_pending_assignments,
            "pending_quizzes": total_pending_quizzes,
            "assignment_marks": overall_assignment_avg,
            "quiz_marks": overall_quiz_avg,
            "completion": round(sum(c["progress"] for c in courses) / len(courses)) if courses else 0,
        },
        "popular_courses": popular_courses,
        "top_instructors": top_instructors,
    }
    return render(request, "dashboard/student.html", context)


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_dashboard(request):
    role = get_user_role(request.user)
    if role == Profile.ROLE_ADMIN:
        instructor_courses = Course.objects.all()
    else:
        instructor_courses = Course.objects.filter(instructor=request.user)
    instructor_course_ids = list(instructor_courses.values_list("id", flat=True))

    student_total = approved_enrollments_qs().filter(course__in=instructor_courses).values("student").distinct().count()
    pending_submission_filter = (
        Q(status=Submission.STATUS_SUBMITTED)
        | Q(status__iexact="pending")
        | Q(status=Submission.STATUS_LATE)
    )
    pending_submissions = Submission.objects.filter(
        assignment__course__in=instructor_courses,
    ).filter(pending_submission_filter).count()

    enrollment_rows = list(
        approved_enrollments_qs().filter(course_id__in=instructor_course_ids)
        .select_related("student", "course")
    )
    completion_benchmark = (
        round(sum(float(enrollment.progress or 0) for enrollment in enrollment_rows) / len(enrollment_rows))
        if enrollment_rows
        else 0
    )

    student_course_counts = {}
    student_progress_values = {}
    for enrollment in enrollment_rows:
        sid = enrollment.student_id
        student_course_counts[sid] = student_course_counts.get(sid, 0) + 1
        student_progress_values.setdefault(sid, []).append(enrollment.progress)

    assignment_percentages = {}
    for submission in Submission.objects.filter(
        assignment__course_id__in=instructor_course_ids,
        score__isnull=False,
    ).select_related("assignment"):
        max_score = float(submission.assignment.max_score or 0)
        if max_score <= 0:
            continue
        pct = (float(submission.score) / max_score) * 100
        assignment_percentages.setdefault(submission.student_id, []).append(pct)

    quiz_percentages = {}
    for attempt in QuizAttempt.objects.filter(
        quiz__course_id__in=instructor_course_ids,
        submitted_at__isnull=False,
    ).select_related("quiz"):
        total_marks = float(attempt.quiz.total_marks or 0)
        if total_marks <= 0:
            continue
        pct = (float(attempt.score) / total_marks) * 100
        quiz_percentages.setdefault(attempt.student_id, []).append(pct)

    top_students = []
    student_ids = set(student_course_counts.keys())
    if student_ids:
        students_map = {
            student.id: student
            for student in User.objects.filter(id__in=student_ids)
        }
        for sid in student_ids:
            student = students_map.get(sid)
            if not student:
                continue
            progress_list = student_progress_values.get(sid, [])
            assignment_list = assignment_percentages.get(sid, [])
            quiz_list = quiz_percentages.get(sid, [])
            avg_progress = round(sum(progress_list) / len(progress_list), 1) if progress_list else 0
            assignment_avg = round(sum(assignment_list) / len(assignment_list), 1) if assignment_list else 0
            quiz_avg = round(sum(quiz_list) / len(quiz_list), 1) if quiz_list else 0

            perf_components = []
            if assignment_list:
                perf_components.append(assignment_avg)
            if quiz_list:
                perf_components.append(quiz_avg)
            overall_score = round(sum(perf_components) / len(perf_components), 1) if perf_components else avg_progress

            top_students.append(
                {
                    "id": sid,
                    "name": get_display_name(student),
                    "username": student.username,
                    "course_count": student_course_counts.get(sid, 0),
                    "avg_progress": avg_progress,
                    "assignment_avg": assignment_avg,
                    "quiz_avg": quiz_avg,
                    "overall_score": overall_score,
                }
            )

        top_students.sort(
            key=lambda row: (row["overall_score"], row["avg_progress"], row["course_count"]),
            reverse=True,
        )
        top_students = top_students[:6]

    student_opinions = [
        {
            "student_name": get_display_name(review.student),
            "course_title": review.course.title,
            "comment": review.comment,
            "course_rating": review.course_rating,
            "instructor_rating": review.instructor_rating,
            "updated_at": review.updated_at,
        }
        for review in CourseReview.objects.filter(course_id__in=instructor_course_ids)
        .exclude(comment="")
        .select_related("student", "course")
        .order_by("-updated_at")[:8]
    ]

    if role == Profile.ROLE_INSTRUCTOR:
        other_courses_qs = Course.objects.filter(
            is_published=True,
            instructor__profile__role=Profile.ROLE_INSTRUCTOR,
        ).exclude(instructor=request.user)
    else:
        other_courses_qs = Course.objects.filter(
            is_published=True,
            instructor__profile__role=Profile.ROLE_INSTRUCTOR,
        )

    other_courses = []
    for course in attach_course_rating_metadata(
        other_courses_qs.select_related("instructor")
        .annotate(enrollment_count=Count("enrollments"))
        .order_by("-enrollment_count", "-rating", "title")[:6]
    ):
        other_courses.append(
            {
                "id": course.id,
                "title": course.title,
                "instructor": get_display_name(course.instructor) if course.instructor else "TBA",
                "level": course.level,
                "category": course.category or "General",
                "enrollment_count": course.enrollment_count,
                "course_rating": course.display_course_rating,
            }
        )

    context = {
        "display_name": get_display_name(request.user),
        "instructor_courses": instructor_courses.order_by("title")[:8],
        "pending_submission_list": Submission.objects.filter(
            assignment__course__in=instructor_courses,
        ).filter(pending_submission_filter).select_related("assignment", "assignment__course", "student")[:8],
        "instructor_stats": {
            "courses": instructor_courses.count(),
            "students": student_total,
            "pending_submissions": pending_submissions,
            "completion": completion_benchmark,
        },
        "top_students": top_students,
        "student_opinions": student_opinions,
        "other_courses": other_courses,
    }
    return render(request, "dashboard/instructor.html", context)


@role_required(Profile.ROLE_ADMIN)
def admin_dashboard(request):
    if request.method == "POST":
        action = request.POST.get("action", "").strip().lower()
        user_id = request.POST.get("user_id", "").strip()

        if action not in {"deactivate_user", "activate_user"}:
            messages.error(request, "Invalid user management action.")
            return redirect("admin_dashboard")

        target_user = (
            User.objects.filter(pk=user_id)
            .select_related("profile")
            .first()
        )
        if not target_user:
            messages.error(request, "User not found.")
            return redirect("admin_dashboard")

        target_profile = getattr(target_user, "profile", None)
        if not target_profile or target_profile.role not in {Profile.ROLE_STUDENT, Profile.ROLE_INSTRUCTOR}:
            messages.error(request, "Only student or instructor accounts can be managed here.")
            return redirect("admin_dashboard")

        if action == "deactivate_user":
            if not target_user.is_active:
                messages.info(request, f"{get_display_name(target_user)} is already inactive.")
            else:
                target_user.is_active = False
                target_user.save(update_fields=["is_active"])
                messages.success(request, f"{get_display_name(target_user)} has been deactivated.")
            return redirect("admin_dashboard")

        if target_user.is_active:
            messages.info(request, f"{get_display_name(target_user)} is already active.")
        else:
            target_user.is_active = True
            target_user.save(update_fields=["is_active"])
            messages.success(request, f"{get_display_name(target_user)} has been activated.")
        return redirect("admin_dashboard")

    total_users = User.objects.count()
    instructor_count = Profile.objects.filter(role=Profile.ROLE_INSTRUCTOR).count()
    student_count = Profile.objects.filter(role=Profile.ROLE_STUDENT).count()
    total_courses = Course.objects.count()
    total_submissions = Submission.objects.count()
    recent_users = list(
        User.objects.select_related("profile")
        .filter(profile__role__in=[Profile.ROLE_STUDENT, Profile.ROLE_INSTRUCTOR])
        .order_by("-date_joined")[:12]
    )

    context = {
        "display_name": get_display_name(request.user),
        "recent_users": recent_users,
        "admin_stats": {
            "total_users": total_users,
            "students": student_count,
            "instructors": instructor_count,
            "courses": total_courses,
            "submissions": total_submissions,
        },
    }
    return render(request, "dashboard/admin.html", context)


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_create_course(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        short_desc = request.POST.get("short_desc", "").strip()
        category = request.POST.get("category", "").strip()
        level = request.POST.get("level", Course.LEVEL_BEGINNER)
        duration_weeks = request.POST.get("duration_weeks", "12").strip()
        enrollment_type = request.POST.get("enrollment_type", Course.ENROLLMENT_OPEN).strip()
        capacity_mode = request.POST.get("capacity_mode", "unlimited").strip().lower()
        max_students_raw = request.POST.get("capacity", "").strip()
        allow_discussions = bool(request.POST.get("allow_discussions"))
        action = request.POST.get("action", "publish").strip().lower()
        description = request.POST.get("description", "").strip()
        thumbnail = request.FILES.get("thumbnail")
        intro_video = request.FILES.get("intro_video")
        raw_tags = request.POST.get("tags", "")

        deduped_tags = []
        seen_tags = set()
        for tag in raw_tags.split(","):
            clean_tag = tag.strip()
            if not clean_tag:
                continue
            normalized = clean_tag.lower()
            if normalized in seen_tags:
                continue
            seen_tags.add(normalized)
            deduped_tags.append(clean_tag)

        normalized_tags = ", ".join(deduped_tags[:12])

        if not title:
            messages.error(request, "Course title is required.")
            return redirect("instructor_create_course")

        try:
            weeks = int(duration_weeks)
        except ValueError:
            weeks = 12

        max_students = None
        if capacity_mode == "limited":
            try:
                max_students = max(1, int(max_students_raw))
            except ValueError:
                messages.error(request, "Please provide a valid max capacity for limited enrollment.")
                return redirect("instructor_create_course")

        course = Course.objects.create(
            title=title,
            short_description=short_desc or ((description[:277] + "...") if len(description) > 280 else description),
            description=description,
            category=category,
            tags=normalized_tags,
            level=level if level in {Course.LEVEL_BEGINNER, Course.LEVEL_INTERMEDIATE, Course.LEVEL_ADVANCED} else Course.LEVEL_BEGINNER,
            duration_weeks=max(1, weeks),
            instructor=request.user,
            enrollment_type=enrollment_type if enrollment_type in {Course.ENROLLMENT_OPEN, Course.ENROLLMENT_APPROVAL} else Course.ENROLLMENT_OPEN,
            max_students=max_students,
            allow_discussions=allow_discussions,
            thumbnail=thumbnail,
            intro_video=intro_video,
            is_published=action == "publish",
        )
        if course.is_published:
            messages.success(request, f"Course '{course.title}' created successfully.")
        else:
            messages.success(request, f"Course '{course.title}' was saved as draft.")
        return redirect("course_detail", course_id=course.id)

    return render(request, "instructor/create_course.html")


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_submissions(request):
    role = get_user_role(request.user)
    if role == Profile.ROLE_ADMIN:
        courses = Course.objects.all()
    else:
        courses = Course.objects.filter(instructor=request.user)

    if request.method == "POST":
        submission_id = request.POST.get("submission_id", "").strip()
        score_raw = request.POST.get("score", "").strip()
        feedback = request.POST.get("feedback", "").strip()
        action = request.POST.get("action", "").strip().lower()
        status = Submission.STATUS_GRADED

        submission = Submission.objects.filter(
            pk=submission_id,
            assignment__course__in=courses,
        ).select_related("assignment").first()

        if not submission:
            messages.error(request, "Submission not found or not accessible.")
            return redirect("instructor_submissions")

        try:
            score_value = float(score_raw)
        except ValueError:
            messages.error(request, "Score must be a valid number.")
            return redirect("instructor_submissions")

        max_score = float(submission.assignment.max_score)
        if score_value < 0 or score_value > max_score:
            messages.error(request, f"Score must be between 0 and {max_score:g}.")
            return redirect("instructor_submissions")

        if action == "resubmit":
            status = Submission.STATUS_SUBMITTED

        if status not in {
            Submission.STATUS_SUBMITTED,
            Submission.STATUS_GRADED,
            Submission.STATUS_LATE,
        }:
            status = Submission.STATUS_GRADED

        submission.score = score_value
        submission.feedback = feedback
        submission.status = status
        submission.save(update_fields=["score", "feedback", "status", "updated_at"])
        if status == Submission.STATUS_SUBMITTED:
            messages.success(request, "Submission marked as pending for resubmission.")
        else:
            messages.success(request, "Submission graded successfully.")
        return redirect("instructor_submissions")

    submissions = Submission.objects.filter(assignment__course__in=courses).select_related(
        "assignment",
        "assignment__course",
        "student",
    )
    course_titles = list(courses.values_list("title", flat=True).order_by("title"))
    return render(
        request,
        "instructor/submissions.html",
        {
            "submissions": submissions,
            "submission_course_titles": course_titles,
            "submission_counts": {
                "all": submissions.count(),
                "pending": submissions.filter(
                    Q(status=Submission.STATUS_SUBMITTED) | Q(status__iexact="pending")
                ).count(),
                "graded": submissions.filter(status=Submission.STATUS_GRADED).count(),
                "late": submissions.filter(status=Submission.STATUS_LATE).count(),
            },
        },
    )


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_manage_content(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    role = get_user_role(request.user)
    if role != Profile.ROLE_ADMIN and course.instructor_id != request.user.id:
        messages.error(request, "You can only edit your own courses.")
        return redirect("courses")

    if request.method == "POST":
        form_type = request.POST.get("form_type", "course_meta").strip()

        if form_type == "delete_assignment":
            assignment_id = request.POST.get("assignment_id", "").strip()
            assignment = course.assignments.filter(pk=assignment_id, archived_at__isnull=True).first()
            if not assignment:
                messages.error(request, "Assignment not found.")
                return redirect("instructor_manage_content", course_id=course.id)

            assignment_title = assignment.title
            assignment.archived_at = timezone.now()
            assignment.is_published = False
            assignment.save(update_fields=["archived_at", "is_published"])

            course.assignment_count = Assignment.objects.filter(
                course=course,
                is_published=True,
                archived_at__isnull=True,
            ).count()
            course.save(update_fields=["assignment_count", "updated_at"])

            messages.success(request, f"Assignment '{assignment_title}' archived.")
            return redirect("instructor_manage_content", course_id=course.id)

        if form_type == "edit_assignment":
            assignment_id = request.POST.get("assignment_id", "").strip()
            assignment = course.assignments.filter(pk=assignment_id, archived_at__isnull=True).first()
            if not assignment:
                messages.error(request, "Assignment not found.")
                return redirect("instructor_manage_content", course_id=course.id)

            title = request.POST.get("edit_assignment_title", "").strip()
            description = request.POST.get("edit_assignment_description", "").strip()
            due_date_raw = request.POST.get("edit_due_date", "").strip()
            publish_at_raw = request.POST.get("edit_publish_at", "").strip()
            max_score_raw = request.POST.get("edit_max_score", str(assignment.max_score)).strip()
            new_attachment = request.FILES.get("edit_assignment_attachment")

            if not title:
                messages.error(request, "Assignment title is required.")
                return redirect("instructor_manage_content", course_id=course.id)

            try:
                max_score = max(1, int(max_score_raw))
            except ValueError:
                max_score = assignment.max_score

            due_date = None
            if due_date_raw:
                parsed_due = parse_datetime(due_date_raw)
                if not parsed_due:
                    messages.error(request, "Please provide a valid due date and time.")
                    return redirect("instructor_manage_content", course_id=course.id)
                if timezone.is_naive(parsed_due):
                    parsed_due = timezone.make_aware(parsed_due, timezone.get_current_timezone())
                due_date = parsed_due

            publish_at = None
            if publish_at_raw:
                parsed_publish = parse_datetime(publish_at_raw)
                if not parsed_publish:
                    messages.error(request, "Please provide a valid publish date and time.")
                    return redirect("instructor_manage_content", course_id=course.id)
                if timezone.is_naive(parsed_publish):
                    parsed_publish = timezone.make_aware(parsed_publish, timezone.get_current_timezone())
                publish_at = parsed_publish

            assignment.title = title
            assignment.description = description
            assignment.due_date = due_date
            assignment.publish_at = publish_at
            assignment.max_score = max_score
            assignment.is_published = bool(request.POST.get("edit_is_assignment_published"))
            if bool(request.POST.get("edit_remove_attachment")):
                assignment.attachment = None
            if new_attachment:
                assignment.attachment = new_attachment

            assignment.save(
                update_fields=[
                    "title",
                    "description",
                    "due_date",
                    "publish_at",
                    "max_score",
                    "is_published",
                    "attachment",
                ]
            )

            course.assignment_count = Assignment.objects.filter(
                course=course,
                is_published=True,
                archived_at__isnull=True,
            ).count()
            course.save(update_fields=["assignment_count", "updated_at"])

            messages.success(request, "Assignment updated successfully.")
            return redirect("instructor_manage_content", course_id=course.id)

        if form_type == "create_assignment":
            title = request.POST.get("assignment_title", "").strip()
            description = request.POST.get("assignment_description", "").strip()
            due_date_raw = request.POST.get("due_date", "").strip()
            publish_at_raw = request.POST.get("publish_at", "").strip()
            max_score_raw = request.POST.get("max_score", "100").strip()
            attachment = request.FILES.get("assignment_attachment")

            if not title:
                messages.error(request, "Assignment title is required.")
                return redirect("instructor_manage_content", course_id=course.id)

            try:
                max_score = max(1, int(max_score_raw))
            except ValueError:
                max_score = 100

            due_date = None
            if due_date_raw:
                parsed_due = parse_datetime(due_date_raw)
                if not parsed_due:
                    messages.error(request, "Please provide a valid due date and time.")
                    return redirect("instructor_manage_content", course_id=course.id)
                if timezone.is_naive(parsed_due):
                    parsed_due = timezone.make_aware(parsed_due, timezone.get_current_timezone())
                due_date = parsed_due

            publish_at = None
            if publish_at_raw:
                parsed_publish = parse_datetime(publish_at_raw)
                if not parsed_publish:
                    messages.error(request, "Please provide a valid publish date and time.")
                    return redirect("instructor_manage_content", course_id=course.id)
                if timezone.is_naive(parsed_publish):
                    parsed_publish = timezone.make_aware(parsed_publish, timezone.get_current_timezone())
                publish_at = parsed_publish

            Assignment.objects.create(
                course=course,
                title=title,
                description=description,
                attachment=attachment,
                due_date=due_date,
                publish_at=publish_at,
                max_score=max_score,
                created_by=request.user,
                is_published=bool(request.POST.get("is_assignment_published")),
            )

            course.assignment_count = Assignment.objects.filter(
                course=course,
                is_published=True,
                archived_at__isnull=True,
            ).count()
            course.save(update_fields=["assignment_count", "updated_at"])

            messages.success(request, "Assignment created successfully.")
            return redirect("instructor_manage_content", course_id=course.id)

        if form_type == "add_module_resource":
            module_id_raw = request.POST.get("module_id", "").strip()
            new_module_title = request.POST.get("new_module_title", "").strip()
            resource_title = request.POST.get("resource_title", "").strip()
            resource_type = request.POST.get("resource_type", ModuleResource.TYPE_FILE).strip()
            resource_description = request.POST.get("resource_description", "").strip()
            external_url = request.POST.get("external_url", "").strip()
            uploaded_video = request.FILES.get("video_file")
            uploaded_file = request.FILES.get("resource_file")

            if not resource_title:
                messages.error(request, "Resource title is required.")
                return redirect("instructor_manage_content", course_id=course.id)

            module_obj = None
            if module_id_raw:
                module_obj = course.modules.filter(pk=module_id_raw).first()
            elif new_module_title:
                next_order = (course.modules.order_by("-order").values_list("order", flat=True).first() or 0) + 1
                module_obj = CourseModule.objects.create(
                    course=course,
                    title=new_module_title,
                    order=next_order,
                    is_published=True,
                )

            if not module_obj:
                messages.error(request, "Choose an existing module or create a new one.")
                return redirect("instructor_manage_content", course_id=course.id)

            if resource_type == ModuleResource.TYPE_VIDEO and not uploaded_video:
                messages.error(request, "Please upload a video file for video resources.")
                return redirect("instructor_manage_content", course_id=course.id)
            if resource_type == ModuleResource.TYPE_FILE and not uploaded_file:
                messages.error(request, "Please upload a file for file resources.")
                return redirect("instructor_manage_content", course_id=course.id)
            if resource_type == ModuleResource.TYPE_LINK and not external_url:
                messages.error(request, "Please provide an external URL for link resources.")
                return redirect("instructor_manage_content", course_id=course.id)

            if resource_type == ModuleResource.TYPE_VIDEO and uploaded_video:
                content_type = (uploaded_video.content_type or "").lower()
                if content_type and not content_type.startswith("video/"):
                    messages.error(request, "Selected video file is not a valid video format.")
                    return redirect("instructor_manage_content", course_id=course.id)

            next_resource_order = (module_obj.resources.order_by("-order").values_list("order", flat=True).first() or 0) + 1
            ModuleResource.objects.create(
                module=module_obj,
                title=resource_title,
                description=resource_description,
                resource_type=resource_type,
                video_file=uploaded_video,
                file=uploaded_file,
                external_url=external_url,
                order=next_resource_order,
                is_published=True,
            )

            course.lecture_count = ModuleResource.objects.filter(
                module__course=course,
                resource_type=ModuleResource.TYPE_VIDEO,
                is_published=True,
            ).count()
            course.assignment_count = Assignment.objects.filter(
                course=course,
                is_published=True,
                archived_at__isnull=True,
            ).count()
            course.quiz_count = Quiz.objects.filter(course=course, is_published=True).count()
            course.save(update_fields=["lecture_count", "assignment_count", "quiz_count", "updated_at"])

            messages.success(request, "Module content uploaded successfully.")
            return redirect("instructor_manage_content", course_id=course.id)

        title = request.POST.get("title", "").strip()
        short_description = request.POST.get("short_description", "").strip()
        description = request.POST.get("description", "").strip()
        category = request.POST.get("category", "").strip()
        level = request.POST.get("level", Course.LEVEL_BEGINNER).strip()
        duration_weeks_raw = request.POST.get("duration_weeks", str(course.duration_weeks)).strip()
        lecture_count_raw = request.POST.get("lecture_count", str(course.lecture_count)).strip()
        assignment_count_raw = request.POST.get("assignment_count", str(course.assignment_count)).strip()
        quiz_count_raw = request.POST.get("quiz_count", str(course.quiz_count)).strip()
        enrollment_type = request.POST.get("enrollment_type", course.enrollment_type).strip()
        capacity_mode = request.POST.get("capacity_mode", "limited" if course.max_students else "unlimited").strip().lower()
        max_students_raw = request.POST.get("max_students", "").strip()
        allow_discussions = bool(request.POST.get("allow_discussions"))

        if not title:
            messages.error(request, "Course title is required.")
            return redirect("instructor_manage_content", course_id=course.id)

        try:
            duration_weeks = max(1, int(duration_weeks_raw))
        except ValueError:
            duration_weeks = course.duration_weeks

        try:
            lecture_count = max(0, int(lecture_count_raw))
        except ValueError:
            lecture_count = course.lecture_count

        try:
            assignment_count = max(0, int(assignment_count_raw))
        except ValueError:
            assignment_count = course.assignment_count

        try:
            quiz_count = max(0, int(quiz_count_raw))
        except ValueError:
            quiz_count = course.quiz_count

        max_students = None
        if capacity_mode == "limited":
            try:
                max_students = max(1, int(max_students_raw))
            except ValueError:
                messages.error(request, "Please provide a valid max capacity for limited courses.")
                return redirect("instructor_manage_content", course_id=course.id)

        course.title = title
        course.short_description = short_description
        course.description = description
        course.category = category
        course.level = level if level in {
            Course.LEVEL_BEGINNER,
            Course.LEVEL_INTERMEDIATE,
            Course.LEVEL_ADVANCED,
        } else Course.LEVEL_BEGINNER
        course.duration_weeks = duration_weeks
        course.lecture_count = lecture_count
        course.assignment_count = assignment_count
        course.quiz_count = quiz_count
        course.enrollment_type = enrollment_type if enrollment_type in {
            Course.ENROLLMENT_OPEN,
            Course.ENROLLMENT_APPROVAL,
        } else Course.ENROLLMENT_OPEN
        course.max_students = max_students
        course.allow_discussions = allow_discussions
        course.is_published = bool(request.POST.get("is_published"))
        thumbnail = request.FILES.get("thumbnail")
        intro_video = request.FILES.get("intro_video")
        if thumbnail:
            course.thumbnail = thumbnail
        if intro_video:
            course.intro_video = intro_video

        course.save()

        messages.success(request, f"Course '{course.title}' updated successfully.")
        return redirect("instructor_manage_content", course_id=course.id)

    modules = course.modules.prefetch_related("resources").all()
    assignments = course.assignments.filter(archived_at__isnull=True).select_related("created_by").order_by("-created_at")
    role_courses = Course.objects.none()
    if role == Profile.ROLE_ADMIN:
        role_courses = Course.objects.filter(instructor__profile__role=Profile.ROLE_INSTRUCTOR)
    else:
        role_courses = Course.objects.filter(instructor=request.user)

    return render(
        request,
        "instructor/manage_content.html",
        {
            "course": course,
            "modules": modules,
            "assignments": assignments,
            "other_courses": role_courses.exclude(pk=course.pk)[:6],
        },
    )


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_quiz_attempts(request, quiz_id):
    quiz_obj = get_object_or_404(Quiz.objects.select_related("course", "course__instructor"), pk=quiz_id)
    role = get_user_role(request.user)
    if role != Profile.ROLE_ADMIN and quiz_obj.course.instructor_id != request.user.id:
        messages.error(request, "You can only evaluate quizzes for your own courses.")
        return redirect("quiz")

    attempts = quiz_obj.attempts.select_related("student").order_by("-submitted_at", "-started_at")
    return render(
        request,
        "instructor/quiz_attempts.html",
        {
            "quiz": quiz_obj,
            "attempts": attempts,
        },
    )


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_edit_quiz(request, quiz_id):
    quiz_obj = get_object_or_404(
        Quiz.objects.select_related("course", "course__instructor").prefetch_related("questions"),
        pk=quiz_id,
    )
    role = get_user_role(request.user)
    if role != Profile.ROLE_ADMIN and quiz_obj.course.instructor_id != request.user.id:
        messages.error(request, "You can only edit quizzes for your own courses.")
        return redirect("quiz")

    if request.method == "POST":
        form_type = request.POST.get("form_type", "").strip()

        if form_type == "quiz_meta":
            title = request.POST.get("title", "").strip()
            total_marks_raw = request.POST.get("total_marks", "").strip()
            time_limit_raw = request.POST.get("time_limit_minutes", "").strip()
            is_published_raw = request.POST.get("is_published")

            if not title:
                messages.error(request, "Quiz title is required.")
                return redirect("instructor_edit_quiz", quiz_id=quiz_obj.id)

            quiz_obj.title = title
            try:
                quiz_obj.total_marks = max(1, int(total_marks_raw or quiz_obj.total_marks))
            except ValueError:
                pass
            try:
                quiz_obj.time_limit_minutes = max(1, int(time_limit_raw or quiz_obj.time_limit_minutes))
            except ValueError:
                pass
            quiz_obj.is_published = bool(is_published_raw)
            quiz_obj.save(update_fields=["title", "total_marks", "time_limit_minutes", "is_published"])
            messages.success(request, "Quiz details updated.")
            return redirect("instructor_edit_quiz", quiz_id=quiz_obj.id)

        if form_type == "add_question":
            question_text = request.POST.get("question_text", "").strip()
            question_type = request.POST.get("question_type", QuizQuestion.TYPE_MCQ).strip()
            marks_raw = request.POST.get("marks", "1").strip()
            correct_answer = request.POST.get("correct_answer", "").strip()
            options_raw = request.POST.get("options", "").strip()

            if not question_text:
                messages.error(request, "Question text is required.")
                return redirect("instructor_edit_quiz", quiz_id=quiz_obj.id)

            try:
                marks = max(1, int(marks_raw))
            except ValueError:
                marks = 1

            if question_type not in {
                QuizQuestion.TYPE_MCQ,
                QuizQuestion.TYPE_TRUE_FALSE,
                QuizQuestion.TYPE_TEXT,
            }:
                question_type = QuizQuestion.TYPE_MCQ

            options_json = None
            if question_type == QuizQuestion.TYPE_MCQ:
                options = [line.strip() for line in options_raw.splitlines() if line.strip()]
                if len(options) < 2:
                    messages.error(request, "MCQ questions require at least 2 options (one per line).")
                    return redirect("instructor_edit_quiz", quiz_id=quiz_obj.id)
                options_json = options

            if question_type == QuizQuestion.TYPE_TRUE_FALSE and not correct_answer:
                correct_answer = "True"

            max_order = quiz_obj.questions.order_by("-order").values_list("order", flat=True).first() or 0
            QuizQuestion.objects.create(
                quiz=quiz_obj,
                question_text=question_text,
                question_type=question_type,
                options_json=options_json,
                correct_answer=correct_answer,
                marks=marks,
                order=max_order + 1,
            )

            messages.success(request, "Question added to quiz.")
            return redirect("instructor_edit_quiz", quiz_id=quiz_obj.id)

        if form_type == "delete_question":
            question_id = request.POST.get("question_id", "").strip()
            question = quiz_obj.questions.filter(pk=question_id).first()
            if question:
                question.delete()
                messages.success(request, "Question deleted.")
            return redirect("instructor_edit_quiz", quiz_id=quiz_obj.id)

    questions = quiz_obj.questions.order_by("order", "id")
    attempt_count = quiz_obj.attempts.count()
    submitted_count = quiz_obj.attempts.filter(submitted_at__isnull=False).count()

    return render(
        request,
        "instructor/edit_quiz.html",
        {
            "quiz": quiz_obj,
            "questions": questions,
            "attempt_count": attempt_count,
            "submitted_count": submitted_count,
            "now": timezone.now(),
        },
    )


@login_required
def profile_page(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    role = get_user_role(request.user)

    if role == Profile.ROLE_INSTRUCTOR and not profile.teacher_id:
        profile.save(update_fields=["teacher_id", "updated_at"])

    if request.method == "POST":
        form_type = request.POST.get("form_type", "general")

        if form_type == "general":
            first_name = request.POST.get("first_name", "").strip()
            last_name = request.POST.get("last_name", "").strip()
            email = request.POST.get("email", "").strip().lower()
            phone = request.POST.get("phone", "").strip()
            city = request.POST.get("city", "").strip()
            country = request.POST.get("country", "").strip()
            bio = request.POST.get("bio", "").strip()

            if not email:
                messages.error(request, "Email is required.")
                return redirect("profile")

            existing = User.objects.filter(email__iexact=email).exclude(pk=request.user.pk)
            if existing.exists():
                messages.error(request, "This email is already used by another account.")
                return redirect("profile")

            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.email = email
            request.user.save(update_fields=["first_name", "last_name", "email"])

            profile.bio = bio[:500]
            profile.phone = phone[:30]
            profile.city = city[:120]
            profile.country = country[:120]
            avatar = request.FILES.get("avatar")
            if avatar:
                profile.avatar = avatar
            profile.save()
            messages.success(request, "Profile updated successfully.")

        elif form_type == "academic":
            if role == Profile.ROLE_STUDENT:
                department = request.POST.get("department", "").strip()
                profile.department = department[:120]
                profile.save(update_fields=["department", "updated_at"])
            else:
                university = request.POST.get("university", "").strip()
                designation = request.POST.get("designation", "").strip()
                profile.university = university[:180]
                profile.designation = designation[:120]
                profile.save(update_fields=["university", "designation", "updated_at"])
            messages.success(request, "Academic profile updated successfully.")

        elif form_type == "security":
            current_password = request.POST.get("current_password", "")
            new_password1 = request.POST.get("new_password1", "")
            new_password2 = request.POST.get("new_password2", "")

            if not request.user.check_password(current_password):
                messages.error(request, "Current password is incorrect.")
                return redirect("profile")

            if len(new_password1) < 8:
                messages.error(request, "New password must be at least 8 characters long.")
                return redirect("profile")

            if new_password1 != new_password2:
                messages.error(request, "New passwords do not match.")
                return redirect("profile")

            request.user.set_password(new_password1)
            request.user.save(update_fields=["password"])
            update_session_auth_hash(request, request.user)
            messages.success(request, "Password updated successfully.")

        return redirect("profile")

    enrolled_courses = []
    grade_summary = []
    all_course_percentages = []
    submission_count = 0
    teaching_courses = []
    instructor_summary = {
        "total_courses": 0,
        "total_students": 0,
        "avg_rating": 0,
        "rated_courses": 0,
    }

    if role == Profile.ROLE_STUDENT:
        enrollment_qs = approved_enrollments_qs().filter(student=request.user).select_related("course", "course__instructor")
        enrolled_courses = [
            {
                "title": enrollment.course.title,
                "instructor": get_display_name(enrollment.course.instructor) if enrollment.course.instructor else "TBA",
                "progress": enrollment.progress,
            }
            for enrollment in enrollment_qs
        ]

        submission_count = Submission.objects.filter(student=request.user).count()

        for enrollment in enrollment_qs:
            course = enrollment.course
            course_percentages = []

            submission_rows = Submission.objects.filter(
                student=request.user,
                assignment__course=course,
                score__isnull=False,
            ).select_related("assignment")
            for submission in submission_rows:
                max_score = float(submission.assignment.max_score or 0)
                if max_score > 0 and submission.score is not None:
                    course_percentages.append((float(submission.score) / max_score) * 100)

            quiz_rows = QuizAttempt.objects.filter(
                student=request.user,
                quiz__course=course,
                submitted_at__isnull=False,
            ).select_related("quiz")
            for attempt in quiz_rows:
                total_marks = float(attempt.quiz.total_marks or 0)
                if total_marks > 0:
                    course_percentages.append((float(attempt.score) / total_marks) * 100)

            if course_percentages:
                avg_percent = sum(course_percentages) / len(course_percentages)
                all_course_percentages.extend(course_percentages)
                grade_summary.append(
                    {
                        "course": course.title,
                        "avg_percent": round(avg_percent, 1),
                    }
                )

        grade_summary.sort(key=lambda item: item["avg_percent"], reverse=True)

    elif role in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN}:
        taught_courses = Course.objects.filter(instructor=request.user) if role == Profile.ROLE_INSTRUCTOR else Course.objects.all()
        teaching_courses = [
            {
                "title": course.title,
                "instructor": get_display_name(course.instructor) if course.instructor else "TBA",
                "student_count": course.enrollments.count(),
                "rating": float(course.rating or 0),
            }
            for course in taught_courses.order_by("title")
        ]

        instructor_summary = {
            "total_courses": taught_courses.count(),
            "total_students": approved_enrollments_qs().filter(course__in=taught_courses).values("student").distinct().count(),
            "avg_rating": float(taught_courses.aggregate(avg=Avg("rating"))["avg"] or 0),
            "rated_courses": taught_courses.filter(rating__gt=0).count(),
        }

    avg_grade = round(sum(all_course_percentages) / len(all_course_percentages), 1) if all_course_percentages else 0

    profile_stats = {
        "course_count": len(enrolled_courses),
        "submitted": submission_count,
        "avg_grade": avg_grade,
    }
    default_teacher_id = profile.teacher_id or build_teacher_id(request.user.id)

    return render(
        request,
        "profile/profile.html",
        {
            "display_name": get_display_name(request.user),
            "profile_obj": profile,
            "is_student": role == Profile.ROLE_STUDENT,
            "is_instructor": role == Profile.ROLE_INSTRUCTOR,
            "is_admin": role == Profile.ROLE_ADMIN,
            "profile_stats": profile_stats,
            "enrolled_courses": enrolled_courses,
            "grade_summary": grade_summary[:6],
            "teaching_courses": teaching_courses,
            "instructor_summary": instructor_summary,
            "default_teacher_id": default_teacher_id,
        },
    )


@login_required
def announcements(request):
    role = get_user_role(request.user)

    if request.method == "POST":
        if role not in {Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN}:
            messages.error(request, "Only instructors and admins can post announcements.")
            return redirect("announcements")

        title = request.POST.get("title", "").strip()
        body = request.POST.get("body", "").strip()
        course_id_raw = request.POST.get("course_id", "").strip()

        if not title or not body:
            messages.error(request, "Title and body are required.")
            return redirect("announcements")

        selected_course = None
        if course_id_raw:
            if role == Profile.ROLE_ADMIN:
                selected_course = Course.objects.filter(pk=course_id_raw).first()
            else:
                selected_course = Course.objects.filter(
                    pk=course_id_raw,
                    instructor=request.user,
                ).first()

            if not selected_course:
                messages.error(request, "Please select a valid course for this announcement.")
                return redirect("announcements")

        Announcement.objects.create(
            course=selected_course,
            author=request.user,
            title=title,
            body=body,
            is_global=selected_course is None,
        )
        messages.success(request, "Announcement posted successfully.")
        return redirect("announcements")

    if role == Profile.ROLE_STUDENT:
        course_ids = approved_enrollments_qs().filter(student=request.user).values_list("course_id", flat=True)
        notices = Announcement.objects.filter(Q(is_global=True) | Q(course_id__in=course_ids))
    elif role == Profile.ROLE_INSTRUCTOR:
        course_ids = Course.objects.filter(instructor=request.user).values_list("id", flat=True)
        notices = Announcement.objects.filter(Q(is_global=True) | Q(course_id__in=course_ids))
    else:
        notices = Announcement.objects.all()

    notices = notices.select_related("course", "author")
    if role == Profile.ROLE_ADMIN:
        posting_courses = Course.objects.order_by("title")
    elif role == Profile.ROLE_INSTRUCTOR:
        posting_courses = Course.objects.filter(instructor=request.user).order_by("title")
    else:
        posting_courses = Course.objects.none()

    return render(
        request,
        "profile/announcements.html",
        {
            "announcements": notices,
            "posting_courses": posting_courses,
        },
    )