import pytest
from django.urls import reverse

from core.forms.courses import CourseCreateForm, CourseReviewForm
from core.models import Course, CourseModule, Enrollment, ModuleCompletion, Profile
from core.selectors.course_queries import get_module_completion_status
from core.services.enrollments import approve_enrollment


pytestmark = [pytest.mark.django_db, pytest.mark.member_b]


DURATION_BOUNDARIES = [
    pytest.param(0, False, id="B-TC-001-duration-below-min"),
    pytest.param(1, True, id="B-TC-002-duration-min"),
    pytest.param(2, True, id="B-TC-003-duration-above-min"),
    pytest.param(51, True, id="B-TC-004-duration-below-max"),
    pytest.param(52, True, id="B-TC-005-duration-max"),
    pytest.param(53, False, id="B-TC-006-duration-above-max"),
]


@pytest.mark.unit
@pytest.mark.bva
@pytest.mark.parametrize(("duration", "expected"), DURATION_BOUNDARIES)
def test_course_duration_boundaries(valid_course_data, duration, expected):
    form = CourseCreateForm(data={**valid_course_data, "duration_weeks": duration})
    assert form.is_valid() is expected


CAPACITY_CLASSES = [
    pytest.param("unlimited", "", True, id="B-TC-007-unlimited-empty-capacity"),
    pytest.param("unlimited", 1, True, id="B-TC-008-unlimited-valid-capacity-ignored"),
    pytest.param("limited", "", False, id="B-TC-009-limited-missing-capacity"),
    pytest.param("limited", 0, False, id="B-TC-010-limited-zero-capacity"),
    pytest.param("limited", 1, True, id="B-TC-011-limited-min-capacity"),
]


@pytest.mark.unit
@pytest.mark.equivalence
@pytest.mark.parametrize(("mode", "capacity", "expected"), CAPACITY_CLASSES)
def test_course_capacity_classes(valid_course_data, mode, capacity, expected):
    form = CourseCreateForm(data={**valid_course_data, "capacity_mode": mode, "capacity": capacity})
    assert form.is_valid() is expected


TITLE_BOUNDARIES = [
    pytest.param(0, False, id="B-TC-012-title-empty"),
    pytest.param(1, True, id="B-TC-013-title-min"),
    pytest.param(200, True, id="B-TC-014-title-max"),
    pytest.param(201, False, id="B-TC-015-title-above-max"),
]


@pytest.mark.unit
@pytest.mark.bva
@pytest.mark.parametrize(("length", "expected"), TITLE_BOUNDARIES)
def test_course_title_boundaries(valid_course_data, length, expected):
    form = CourseCreateForm(data={**valid_course_data, "title": "x" * length})
    assert form.is_valid() is expected


REVIEW_BOUNDARIES = [
    pytest.param("course_rating", 0, False, id="B-TC-016-course-rating-below-min"),
    pytest.param("course_rating", 1, True, id="B-TC-017-course-rating-min"),
    pytest.param("course_rating", 5, True, id="B-TC-018-course-rating-max"),
    pytest.param("course_rating", 6, False, id="B-TC-019-course-rating-above-max"),
    pytest.param("instructor_rating", 0, False, id="B-TC-020-instructor-rating-below-min"),
    pytest.param("instructor_rating", 1, True, id="B-TC-021-instructor-rating-min"),
    pytest.param("instructor_rating", 5, True, id="B-TC-022-instructor-rating-max"),
    pytest.param("instructor_rating", 6, False, id="B-TC-023-instructor-rating-above-max"),
]


@pytest.mark.unit
@pytest.mark.bva
@pytest.mark.parametrize(("field", "value", "expected"), REVIEW_BOUNDARIES)
def test_course_review_rating_boundaries(field, value, expected):
    data = {"course_rating": 3, "instructor_rating": 3, "comment": "Useful course"}
    data[field] = value
    assert CourseReviewForm(data=data).is_valid() is expected


CAPACITY_DECISIONS = [
    pytest.param(None, 0, False, id="B-TC-024-no-capacity-limit"),
    pytest.param(0, 0, False, id="B-TC-025-zero-treated-unlimited"),
    pytest.param(1, 0, False, id="B-TC-026-space-available"),
    pytest.param(1, 1, True, id="B-TC-027-capacity-reached"),
]


@pytest.mark.unit
@pytest.mark.decision_table
@pytest.mark.parametrize(("maximum", "approved_count", "expected"), CAPACITY_DECISIONS)
def test_course_capacity_decisions(course_factory, user_factory, maximum, approved_count, expected):
    course = course_factory(max_students=maximum)
    for index in range(approved_count):
        Enrollment.objects.create(
            student=user_factory(username=f"capacity-student-{index}"),
            course=course,
            status=Enrollment.STATUS_APPROVED,
        )
    assert course.is_at_capacity() is expected


@pytest.mark.unit
@pytest.mark.basis_path
def test_b_tc_028_approve_enrollment_already_approved_returns_false(approved_enrollment):
    assert approve_enrollment(approved_enrollment) is False


@pytest.mark.unit
@pytest.mark.basis_path
def test_b_tc_029_approve_pending_enrollment_succeeds(student, course):
    enrollment = Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_PENDING)
    assert approve_enrollment(enrollment) is True
    enrollment.refresh_from_db()
    assert enrollment.status == Enrollment.STATUS_APPROVED


@pytest.mark.unit
@pytest.mark.basis_path
def test_b_tc_030_approve_pending_enrollment_rejects_full_course(student, course, user_factory):
    course.max_students = 1
    course.save(update_fields=["max_students"])
    Enrollment.objects.create(student=user_factory(username="occupant"), course=course)
    pending = Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_PENDING)
    with pytest.raises(ValueError, match="maximum capacity"):
        approve_enrollment(pending)


COMPLETION_PATHS = [
    pytest.param(0, 0, (0, 0, False), id="B-TC-031-no-published-modules"),
    pytest.param(1, 0, (1, 0, False), id="B-TC-032-one-incomplete-module"),
    pytest.param(1, 1, (1, 1, True), id="B-TC-033-one-complete-module"),
    pytest.param(2, 1, (2, 1, False), id="B-TC-034-partial-multiple-modules"),
]


@pytest.mark.unit
@pytest.mark.basis_path
@pytest.mark.parametrize(("module_count", "complete_count", "expected"), COMPLETION_PATHS)
def test_module_completion_status(approved_enrollment, module_count, complete_count, expected):
    modules = [
        CourseModule.objects.create(course=approved_enrollment.course, title=f"Module {index}", order=index)
        for index in range(module_count)
    ]
    for module in modules[:complete_count]:
        ModuleCompletion.objects.create(enrollment=approved_enrollment, module=module)
    assert get_module_completion_status(approved_enrollment) == expected


ENROLLMENT_PATHS = [
    pytest.param("anonymous", 0, None, id="B-TC-035-anonymous-enrollment"),
    pytest.param("get", 0, None, id="B-TC-036-get-does-not-enroll"),
    pytest.param("instructor", 0, None, id="B-TC-037-instructor-cannot-enroll"),
    pytest.param("ended", 0, None, id="B-TC-038-ended-course"),
    pytest.param("existing-approved", 1, Enrollment.STATUS_APPROVED, id="B-TC-039-already-approved"),
    pytest.param("existing-pending", 1, Enrollment.STATUS_PENDING, id="B-TC-040-already-pending"),
    pytest.param("full", 0, None, id="B-TC-041-full-course"),
    pytest.param("approval", 1, Enrollment.STATUS_PENDING, id="B-TC-042-approval-request"),
    pytest.param("open", 1, Enrollment.STATUS_APPROVED, id="B-TC-043-open-enrollment"),
    pytest.param("unpublished", 0, None, id="B-TC-044-unpublished-course"),
]


@pytest.mark.integration
@pytest.mark.decision_table
@pytest.mark.parametrize(("scenario", "expected_count", "expected_status"), ENROLLMENT_PATHS)
def test_course_enrollment_paths(
    client, student, instructor, course, user_factory, scenario, expected_count, expected_status
):
    method = "post"
    if scenario == "anonymous":
        pass
    elif scenario == "instructor":
        client.force_login(instructor)
    else:
        client.force_login(student)
    if scenario == "get":
        method = "get"
    elif scenario == "ended":
        course.is_ended = True
        course.save(update_fields=["is_ended"])
    elif scenario == "existing-approved":
        Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_APPROVED)
    elif scenario == "existing-pending":
        Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_PENDING)
    elif scenario == "full":
        course.max_students = 1
        course.save(update_fields=["max_students"])
        Enrollment.objects.create(student=user_factory(username="full-occupant"), course=course)
    elif scenario == "approval":
        course.enrollment_type = Course.ENROLLMENT_APPROVAL
        course.save(update_fields=["enrollment_type"])
    elif scenario == "unpublished":
        course.is_published = False
        course.save(update_fields=["is_published"])

    response = getattr(client, method)(reverse("course_enroll", args=[course.id]))

    assert response.status_code in {302, 404}
    enrollment = Enrollment.objects.filter(student=student, course=course).first()
    assert Enrollment.objects.filter(student=student, course=course).count() == expected_count
    if expected_status:
        assert enrollment.status == expected_status


DISCUSSION_PATHS = [
    pytest.param("approved-student", True, True, 200, id="B-TC-045-enrolled-student-discussion"),
    pytest.param("student", True, False, 302, id="B-TC-046-non-enrolled-student-discussion"),
    pytest.param("approved-student", False, True, 302, id="B-TC-047-disabled-student-discussion"),
    pytest.param("instructor", False, False, 200, id="B-TC-048-owner-can-view-disabled-discussion"),
]


@pytest.mark.integration
@pytest.mark.decision_table
@pytest.mark.parametrize(("actor", "enabled", "enrolled", "expected_status"), DISCUSSION_PATHS)
def test_course_discussion_access(client, student, instructor, course, actor, enabled, enrolled, expected_status):
    course.allow_discussions = enabled
    course.save(update_fields=["allow_discussions"])
    if enrolled:
        Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_APPROVED)
    user = instructor if actor == "instructor" else student
    client.force_login(user)
    response = client.get(reverse("course_discussion", args=[course.id]))
    assert response.status_code == expected_status


@pytest.mark.integration
def test_b_tc_049_certificate_rejected_before_course_ends(client, approved_enrollment):
    client.force_login(approved_enrollment.student)
    response = client.get(reverse("course_certificate_download", args=[approved_enrollment.course_id]))
    assert response.status_code == 302
    assert response.url == reverse("course_detail", args=[approved_enrollment.course_id])


@pytest.mark.integration
def test_b_tc_050_certificate_download_for_completed_ended_course(client, approved_enrollment):
    course = approved_enrollment.course
    course.is_ended = True
    course.save(update_fields=["is_ended"])
    module = CourseModule.objects.create(course=course, title="Final module")
    ModuleCompletion.objects.create(enrollment=approved_enrollment, module=module)
    client.force_login(approved_enrollment.student)

    response = client.get(reverse("course_certificate_download", args=[course.id]))

    assert response.status_code == 200
    assert response["Content-Disposition"].startswith("attachment;")

