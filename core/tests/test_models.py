from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from ..models import Course, Enrollment, Profile
from .factories import create_course, create_user


class ModelConstraintTests(TestCase):
    def setUp(self):
        self.instructor = create_user(username="inst1", role=Profile.ROLE_INSTRUCTOR)
        self.student = create_user(username="student1", role=Profile.ROLE_STUDENT)
        self.course = create_course(instructor=self.instructor, title="Algorithms 101")

    def test_enrollment_is_unique_per_student_and_course(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        with self.assertRaises(IntegrityError):
            Enrollment.objects.create(student=self.student, course=self.course)

    def test_enrollment_progress_validator(self):
        enrollment = Enrollment(student=self.student, course=self.course, progress=120)
        with self.assertRaises(ValidationError):
            enrollment.full_clean()

    def test_course_rating_validator(self):
        course = Course(title="Invalid Rating", category="Test", rating=7.5, instructor=self.instructor)
        with self.assertRaises(ValidationError):
            course.full_clean()
