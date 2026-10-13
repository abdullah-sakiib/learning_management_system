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
from ..forms import ProfileGeneralForm
from ..permissions import get_user_role, role_required
from ..selectors.course_queries import (
    approved_enrollments_qs, attach_course_rating_metadata,
    get_module_completion_status,
)
from ..utils import build_teacher_id, get_display_name


@login_required
def settings_page(request):
    return render(request, "core/settings.html")


@login_required
def profile_page(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    role = get_user_role(request.user)

    if role == Profile.ROLE_INSTRUCTOR and not profile.teacher_id:
        profile.save(update_fields=["teacher_id", "updated_at"])

    if request.method == "POST":
        form_type = request.POST.get("form_type", "general")

        if form_type == "general":
            form = ProfileGeneralForm(request.POST, request.FILES, user=request.user)
            if not form.is_valid():
                for errors in form.errors.values():
                    for error in errors:
                        messages.error(request, error)
                return redirect("profile")

            request.user.first_name = form.cleaned_data["first_name"].strip()
            request.user.last_name = form.cleaned_data["last_name"].strip()
            request.user.email = form.cleaned_data["email"]
            request.user.save(update_fields=["first_name", "last_name", "email"])

            profile.bio = form.cleaned_data["bio"].strip()
            profile.phone = form.cleaned_data["phone"].strip()
            profile.city = form.cleaned_data["city"].strip()
            profile.country = form.cleaned_data["country"].strip()
            avatar = form.cleaned_data.get("avatar")
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
        enrollment_qs = list(
            approved_enrollments_qs().filter(student=request.user).select_related("course", "course__instructor")
        )
        enrollment_ids = [enrollment.id for enrollment in enrollment_qs]
        course_ids = [enrollment.course_id for enrollment in enrollment_qs]
        module_totals_by_course = {
            row["course_id"]: row["total"]
            for row in CourseModule.objects.filter(
                course_id__in=course_ids,
                is_published=True,
            ).values("course_id").annotate(total=Count("id"))
        }
        completed_modules_by_enrollment = {
            row["enrollment_id"]: row["completed"]
            for row in ModuleCompletion.objects.filter(
                enrollment_id__in=enrollment_ids,
                module__is_published=True,
            ).values("enrollment_id").annotate(completed=Count("module", distinct=True))
        }

        enrolled_courses = [
            {
                "id": enrollment.course.id,
                "title": enrollment.course.title,
                "instructor": get_display_name(enrollment.course.instructor) if enrollment.course.instructor else "TBA",
                "progress": enrollment.progress,
                "is_course_ended": enrollment.course.is_ended,
                "certificate_available": (
                    enrollment.course.is_ended
                    and module_totals_by_course.get(enrollment.course_id, 0) > 0
                    and completed_modules_by_enrollment.get(enrollment.id, 0) >= module_totals_by_course.get(enrollment.course_id, 0)
                ),
            }
            for enrollment in enrollment_qs
        ]
        certificate_count = len([course for course in enrolled_courses if course["certificate_available"]])

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
        "certificates": certificate_count if role == Profile.ROLE_STUDENT else 0,
    }
    default_teacher_id = profile.teacher_id or build_teacher_id(request.user.id)

    return render(
        request,
        "core/profile/profile.html",
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
        "core/profile/announcements.html",
        {
            "announcements": notices,
            "posting_courses": posting_courses,
        },
    )
