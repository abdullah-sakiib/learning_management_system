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
from ..forms import CourseReviewForm
from ..permissions import get_user_role, role_required
from ..selectors.course_queries import (
    approved_enrollments_qs, attach_course_rating_metadata,
    get_module_completion_status,
)
from ..utils import build_teacher_id, get_display_name


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
    return render(request, "core/courses/catalog.html", context)


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
    return render(request, "core/courses/catalog.html", context)


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
    return render(request, "core/courses/detail.html", context)


@role_required(Profile.ROLE_STUDENT)
def course_submit_review(request, course_id):
    if request.method != "POST":
        return redirect("course_detail", course_id=course_id)

    course = get_object_or_404(Course, pk=course_id, is_published=True)
    if not approved_enrollments_qs().filter(student=request.user, course=course).exists():
        messages.error(request, "You can only review courses you are enrolled in.")
        return redirect("course_detail", course_id=course.id)

    form = CourseReviewForm(request.POST)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect("course_detail", course_id=course.id)

    CourseReview.objects.update_or_create(
        course=course,
        student=request.user,
        defaults={
            "course_rating": form.cleaned_data["course_rating"],
            "instructor_rating": form.cleaned_data["instructor_rating"],
            "comment": form.cleaned_data["comment"],
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
        "core/courses/content.html",
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


@role_required(Profile.ROLE_STUDENT)
def course_certificate_download(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    enrollment = approved_enrollments_qs().filter(student=request.user, course=course).first()

    if not enrollment:
        messages.error(request, "You must be enrolled in this course to download a certificate.")
        return redirect("student_dashboard")

    if not course.is_ended:
        messages.error(request, "This course is not ended yet. Certificate is not available.")
        return redirect("course_detail", course_id=course.id)

    total_modules, completed_modules, is_completed = get_module_completion_status(enrollment)
    if not is_completed:
        messages.error(
            request,
            f"Certificate is locked. Complete all modules first ({completed_modules}/{total_modules}).",
        )
        return redirect("course_content", course_id=course.id)

    now_local = timezone.localtime(timezone.now())
    certificate_code = f"EDU-{course.id:05d}-{request.user.id:05d}-{now_local:%Y%m%d}"
    certificate_html = render_to_string(
        "core/courses/certificate_download.html",
        {
            "course": course,
            "student_name": get_display_name(request.user),
            "instructor_name": get_display_name(course.instructor) if course.instructor else "Course Instructor",
            "issued_on": now_local,
            "certificate_code": certificate_code,
        },
    )

    safe_course_name = slugify(course.title) or f"course-{course.id}"
    response = HttpResponse(certificate_html, content_type="text/html; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{safe_course_name}-certificate.html"'
    return response


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
        "core/courses/discussion.html",
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

    if course.is_ended:
        messages.error(request, "This course has ended. New enrollments are closed.")
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
