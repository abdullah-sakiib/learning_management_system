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
from ..forms import CourseCreateForm
from ..services.enrollments import approve_enrollment, remove_enrollment
from ..permissions import get_user_role, role_required
from ..selectors.course_queries import (
    approved_enrollments_qs, attach_course_rating_metadata,
    get_module_completion_status,
)
from ..utils import build_teacher_id, get_display_name


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
            try:
                changed = approve_enrollment(enrollment)
            except ValueError:
                messages.error(request, f"Cannot approve {student_name}. {course_title} is already at max capacity.")
                return redirect("instructor_my_courses")
            if not changed:
                messages.info(request, f"{student_name} is already approved for {course_title}.")
                return redirect("instructor_my_courses")
            messages.success(request, f"Approved {student_name} for {course_title}.")
            return redirect("instructor_my_courses")

        if action == "reject_enrollment":
            remove_enrollment(enrollment)
            messages.success(request, f"Rejected enrollment request of {student_name} for {course_title}.")
            return redirect("instructor_my_courses")

        remove_enrollment(enrollment)
        messages.success(request, f"Removed {student_name} from {course_title}.")
        return redirect("instructor_my_courses")

    course_list = list(instructor_courses.select_related("instructor").order_by("title"))
    if not course_list:
        return render(
            request,
            "core/instructor/my_courses.html",
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
    return render(request, "core/instructor/my_courses.html", context)


@role_required(Profile.ROLE_INSTRUCTOR, Profile.ROLE_ADMIN)
def instructor_create_course(request):
    if request.method == "POST":
        form = CourseCreateForm(request.POST, request.FILES)
        if form.is_valid():
            course = form.save(instructor=request.user)
            message = (
                f"Course '{course.title}' created successfully."
                if course.is_published
                else f"Course '{course.title}' was saved as draft."
            )
            messages.success(request, message)
            return redirect("course_detail", course_id=course.id)
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
    else:
        form = CourseCreateForm()

    return render(request, "core/instructor/create_course.html", {"form": form})


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
        "core/instructor/submissions.html",
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

        if form_type == "end_course":
            if course.is_ended:
                messages.info(request, "This course is already ended.")
                return redirect("instructor_manage_content", course_id=course.id)

            course.is_ended = True
            course.ended_at = timezone.now()
            course.save(update_fields=["is_ended", "ended_at", "updated_at"])
            messages.success(
                request,
                "Course ended successfully. Students who completed all modules can now download certificates.",
            )
            return redirect("instructor_manage_content", course_id=course.id)

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
        "core/instructor/manage_content.html",
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
        "core/instructor/quiz_attempts.html",
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
        "core/instructor/edit_quiz.html",
        {
            "quiz": quiz_obj,
            "questions": questions,
            "attempt_count": attempt_count,
            "submitted_count": submitted_count,
            "now": timezone.now(),
        },
    )
