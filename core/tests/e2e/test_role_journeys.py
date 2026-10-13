import pytest

from core.models import Course, Enrollment, Profile, Quiz, QuizQuestion
from core.tests.conftest import DEFAULT_PASSWORD

from .page_objects.auth import LoginPage, RegistrationPage
from .page_objects.courses import CourseDetailPage, QuizTakePage


pytestmark = [pytest.mark.selenium, pytest.mark.django_db(transaction=True)]


def test_student_registration_journey(browser, live_server, django_user_model):
    RegistrationPage(browser, live_server.url).register_student(
        first_name="Selenium",
        last_name="Student",
        email="selenium.student@example.com",
        password=DEFAULT_PASSWORD,
    )
    assert "/dashboard/student/" in browser.current_url
    assert django_user_model.objects.filter(email="selenium.student@example.com").exists()


def test_student_open_enrollment_journey(browser, live_server, student, course):
    LoginPage(browser, live_server.url).login(student.email, DEFAULT_PASSWORD)
    CourseDetailPage(browser, live_server.url).enroll(course.id)
    enrollment = Enrollment.objects.get(student_id=student.id, course_id=course.id)
    assert enrollment.status == Enrollment.STATUS_APPROVED


def test_student_quiz_submission_journey(browser, live_server, student, course):
    Enrollment.objects.create(student=student, course=course, status=Enrollment.STATUS_APPROVED)
    quiz = Quiz.objects.create(course=course, title="Selenium Quiz", created_by=course.instructor)
    question = QuizQuestion.objects.create(
        quiz=quiz,
        question_text="Testing improves quality.",
        question_type=QuizQuestion.TYPE_TRUE_FALSE,
        correct_answer="True",
        marks=5,
    )
    LoginPage(browser, live_server.url).login(student.email, DEFAULT_PASSWORD)
    QuizTakePage(browser, live_server.url).submit_answer(quiz.id, question.id, "True")
    attempt = Quiz.objects.get(pk=quiz.pk).attempts.get(student_id=student.id)
    assert attempt.score == 5


@pytest.mark.parametrize(
    ("role", "expected_path"),
    [
        pytest.param(Profile.ROLE_INSTRUCTOR, "/dashboard/instructor/", id="selenium-instructor-login"),
        pytest.param(Profile.ROLE_ADMIN, "/dashboard/admin/", id="selenium-admin-login"),
    ],
)
def test_staff_role_login_journey(browser, live_server, user_factory, role, expected_path):
    user = user_factory(role=role, username=f"selenium-{role}", is_staff=role == Profile.ROLE_ADMIN)
    LoginPage(browser, live_server.url).login(user.email, DEFAULT_PASSWORD)
    assert expected_path in browser.current_url


