from django.db.models import Avg, Count

from ..models import CourseModule, CourseReview, Enrollment, ModuleCompletion


def approved_enrollments_qs():
    return Enrollment.objects.filter(status=Enrollment.STATUS_APPROVED)


def get_module_completion_status(enrollment):
    total_modules = CourseModule.objects.filter(
        course=enrollment.course,
        is_published=True,
    ).count()
    if total_modules <= 0:
        return 0, 0, False

    completed_modules = (
        ModuleCompletion.objects.filter(
            enrollment=enrollment,
            module__course=enrollment.course,
            module__is_published=True,
        )
        .values("module_id")
        .distinct()
        .count()
    )
    return total_modules, completed_modules, completed_modules >= total_modules


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
        course_stats_row = course_stats.get(course.id)
        instructor_stats_row = instructor_stats.get(course.instructor_id)
        course.display_course_rating = (
            round(float(course_stats_row["avg_course"]), 1)
            if course_stats_row and course_stats_row["avg_course"] is not None
            else float(course.rating or 0)
        )
        course.course_review_count = course_stats_row["review_count"] if course_stats_row else 0
        course.display_instructor_rating = (
            round(float(instructor_stats_row["avg_instructor"]), 1)
            if instructor_stats_row and instructor_stats_row["avg_instructor"] is not None
            else 0
        )
        course.instructor_review_count = instructor_stats_row["review_count"] if instructor_stats_row else 0

    return course_list
