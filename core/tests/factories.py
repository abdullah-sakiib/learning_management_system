from django.contrib.auth import get_user_model

from ..models import Course, Profile


User = get_user_model()


def create_user(*, username, role, password="pass12345"):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password=password,
    )
    Profile.objects.create(user=user, role=role)
    return user


def create_course(*, instructor, title="Data Structures"):
    return Course.objects.create(
        title=title,
        category="Computer Science",
        level=Course.LEVEL_BEGINNER,
        instructor=instructor,
        is_published=True,
    )
