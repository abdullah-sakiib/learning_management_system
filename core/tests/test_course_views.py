from django.test import TestCase
from django.urls import reverse

from ..models import Enrollment, Profile
from .factories import create_course, create_user


class CourseFlowTests(TestCase):
    def setUp(self):
        self.instructor = create_user(username="inst2", role=Profile.ROLE_INSTRUCTOR)
        self.student = create_user(username="student3", role=Profile.ROLE_STUDENT)
        self.course = create_course(instructor=self.instructor)

    def test_course_unenroll_removes_enrollment(self):
        Enrollment.objects.create(student=self.student, course=self.course)
        self.client.login(username="student3", password="pass12345")
        response = self.client.post(reverse("course_unenroll", args=[self.course.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Enrollment.objects.filter(student=self.student, course=self.course).exists())

    def test_anonymous_user_cannot_open_course_catalog(self):
        response = self.client.get(reverse("courses"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
