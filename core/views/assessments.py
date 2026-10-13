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
from ..forms import AssignmentSubmissionForm, QuizCreateForm
from ..services.assessments import submit_quiz_attempt
from ..permissions import get_user_role, role_required
from ..selectors.course_queries import (
    approved_enrollments_qs, attach_course_rating_metadata,
    get_module_completion_status,
)
from ..utils import build_teacher_id, get_display_name


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

        form = AssignmentSubmissionForm(request.POST, request.FILES)
        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("assignments")

        assignment_id = form.cleaned_data["assignment_id"]
        assignment_title = form.cleaned_data["assignment_title"].strip()
        upload = form.cleaned_data["submission"]
        comment = form.cleaned_data["comment"].strip()

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
        "core/assessment/assignment.html",
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
        "core/assessment/grades.html",
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

        form = QuizCreateForm(request.POST)
        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect("quiz")

        selected_course = instructor_courses.filter(pk=form.cleaned_data["course_id"]).first()
        if not selected_course:
            messages.error(request, "Please choose a valid course.")
            return redirect("quiz")

        quiz_obj = Quiz.objects.create(
            course=selected_course,
            title=form.cleaned_data["title"],
            total_marks=form.cleaned_data["total_marks"],
            time_limit_minutes=form.cleaned_data["time_limit_minutes"],
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
        "core/assessment/quiz.html",
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

        answers = {
            question.id: request.POST.get(f"answer_{question.id}", "")
            for question in questions
        }
        total_score = submit_quiz_attempt(attempt, questions, answers)
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
        "core/assessment/quiz_take.html",
        {
            "quiz_obj": quiz_obj,
            "questions": questions,
            "question_rows": question_rows,
            "attempt": attempt,
            "is_submitted": attempt.submitted_at is not None,
        },
    )
