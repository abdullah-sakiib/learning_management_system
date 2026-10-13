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
from ..permissions import get_user_role, role_required
from ..selectors.course_queries import (
    approved_enrollments_qs, attach_course_rating_metadata,
    get_module_completion_status,
)
from ..utils import build_teacher_id, get_display_name


@role_required(Profile.ROLE_STUDENT)
def student_dashboard(request):
    now = timezone.now()
    enrollment_qs = list(approved_enrollments_qs().filter(student=request.user).select_related("course", "course__instructor"))
    course_ids = [e.course_id for e in enrollment_qs]
    enrolled_course_ids = set(course_ids)
    enrollment_ids = [e.id for e in enrollment_qs]

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

        total_modules = module_totals_by_course.get(cid, 0)
        completed_modules = completed_modules_by_enrollment.get(enrollment.id, 0)
        all_modules_completed = total_modules > 0 and completed_modules >= total_modules
        certificate_available = enrollment.course.is_ended and all_modules_completed

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
                "is_course_ended": enrollment.course.is_ended,
                "certificate_available": certificate_available,
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
    return render(request, "core/dashboard/student.html", context)


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
    return render(request, "core/dashboard/instructor.html", context)


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
    return render(request, "core/dashboard/admin.html", context)
