from django.test import TestCase
from django.urls import reverse

from ..models import Profile
from .factories import create_user


class RolePermissionTests(TestCase):
    def test_student_cannot_open_admin_dashboard(self):
        create_user(username="student4", role=Profile.ROLE_STUDENT)
        self.client.login(username="student4", password="pass12345")
        response = self.client.get(reverse("admin_dashboard"))
        self.assertRedirects(response, reverse("student_dashboard"), fetch_redirect_response=False)
