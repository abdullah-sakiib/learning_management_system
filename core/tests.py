from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Course, Enrollment, Profile


User = get_user_model()


class ModelConstraintTests(TestCase):
	def setUp(self):
		self.instructor = User.objects.create_user(
			username="inst1",
			email="inst1@example.com",
			password="pass12345",
		)
		self.student = User.objects.create_user(
			username="student1",
			email="student1@example.com",
			password="pass12345",
		)
		Profile.objects.create(user=self.student, role=Profile.ROLE_STUDENT)

		self.course = Course.objects.create(
			title="Algorithms 101",
			category="Computer Science",
			level=Course.LEVEL_BEGINNER,
			instructor=self.instructor,
		)

	def test_enrollment_unique_together(self):
		Enrollment.objects.create(student=self.student, course=self.course)
		with self.assertRaises(Exception):
			Enrollment.objects.create(student=self.student, course=self.course)

	def test_enrollment_progress_validator(self):
		enrollment = Enrollment(student=self.student, course=self.course, progress=120)
		with self.assertRaises(ValidationError):
			enrollment.full_clean()

	def test_course_rating_validator(self):
		course = Course(
			title="Invalid Rating Course",
			category="Test",
			rating=7.5,
			instructor=self.instructor,
		)
		with self.assertRaises(ValidationError):
			course.full_clean()


class SecurityAndFlowTests(TestCase):
	def setUp(self):
		self.instructor = User.objects.create_user(
			username="inst2",
			email="inst2@example.com",
			password="pass12345",
		)
		Profile.objects.create(user=self.instructor, role=Profile.ROLE_INSTRUCTOR)

		self.student = User.objects.create_user(
			username="student2",
			email="student2@example.com",
			password="pass12345",
		)
		Profile.objects.create(user=self.student, role=Profile.ROLE_STUDENT)

		self.course = Course.objects.create(
			title="Data Structures",
			category="Computer Science",
			level=Course.LEVEL_BEGINNER,
			instructor=self.instructor,
			is_published=True,
		)

	def test_register_cannot_create_admin_profile(self):
		response = self.client.post(
			reverse("register"),
			{
				"role": Profile.ROLE_ADMIN,
				"first_name": "Alice",
				"last_name": "Admin",
				"email": "alice@example.com",
				"password1": "safePass123",
				"password2": "safePass123",
				"terms": "on",
			},
		)

		self.assertEqual(response.status_code, 302)
		user = User.objects.get(email="alice@example.com")
		self.assertEqual(user.profile.role, Profile.ROLE_STUDENT)

	def test_logout_requires_post(self):
		self.client.login(username="student2", password="pass12345")
		self.client.get(reverse("logout"))
		self.assertIn("_auth_user_id", self.client.session)

	def test_course_unenroll_removes_enrollment(self):
		Enrollment.objects.create(student=self.student, course=self.course)
		self.client.login(username="student2", password="pass12345")
		response = self.client.post(reverse("course_unenroll", args=[self.course.id]))

		self.assertEqual(response.status_code, 302)
		self.assertFalse(
			Enrollment.objects.filter(student=self.student, course=self.course).exists()
		)
