from collections.abc import Callable

import pytest

from core.models import Course, Enrollment, Profile


DEFAULT_PASSWORD = "SafePass934!x"


@pytest.fixture
def user_factory(django_user_model) -> Callable:
    counter = 0

    def create_user(*, role=Profile.ROLE_STUDENT, username=None, password=DEFAULT_PASSWORD, **fields):
        nonlocal counter
        counter += 1
        username = username or f"user{counter}"
        user = django_user_model.objects.create_user(
            username=username,
            email=fields.pop("email", f"{username}@example.com"),
            password=password,
            **fields,
        )
        Profile.objects.create(user=user, role=role)
        return user

    return create_user


@pytest.fixture
def student(user_factory):
    return user_factory(role=Profile.ROLE_STUDENT, username="student")


@pytest.fixture
def instructor(user_factory):
    return user_factory(role=Profile.ROLE_INSTRUCTOR, username="instructor")


@pytest.fixture
def admin_user(user_factory):
    return user_factory(role=Profile.ROLE_ADMIN, username="administrator", is_staff=True)


@pytest.fixture
def course_factory(instructor) -> Callable:
    counter = 0

    def create_course(**fields):
        nonlocal counter
        counter += 1
        defaults = {
            "title": f"Course {counter}",
            "category": "Computer Science",
            "level": Course.LEVEL_BEGINNER,
            "instructor": instructor,
            "is_published": True,
        }
        defaults.update(fields)
        return Course.objects.create(**defaults)

    return create_course


@pytest.fixture
def course(course_factory):
    return course_factory(title="Software Testing")


@pytest.fixture
def approved_enrollment(student, course):
    return Enrollment.objects.create(
        student=student,
        course=course,
        status=Enrollment.STATUS_APPROVED,
    )


@pytest.fixture
def login(client):
    def login_user(user, password=DEFAULT_PASSWORD):
        assert client.login(username=user.username, password=password)
        return client

    return login_user


@pytest.fixture
def valid_registration_data():
    return {
        "role": Profile.ROLE_STUDENT,
        "first_name": "Test",
        "last_name": "Student",
        "email": "new.student@example.com",
        "password1": DEFAULT_PASSWORD,
        "password2": DEFAULT_PASSWORD,
        "terms": True,
    }


@pytest.fixture
def valid_course_data():
    return {
        "title": "Quality Assurance",
        "short_desc": "A practical software-quality course",
        "description": "Learn testing techniques with examples.",
        "category": "Computer Science",
        "tags": "testing, quality",
        "level": Course.LEVEL_BEGINNER,
        "duration_weeks": 12,
        "enrollment_type": Course.ENROLLMENT_OPEN,
        "allow_discussions": True,
        "capacity_mode": "unlimited",
        "capacity": "",
        "action": "publish",
    }
