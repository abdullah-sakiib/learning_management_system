from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ..models import Profile
from .factories import create_user


User = get_user_model()


class AuthenticationViewTests(TestCase):
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
        self.assertEqual(User.objects.get(email="alice@example.com").profile.role, Profile.ROLE_STUDENT)

    def test_logout_requires_post(self):
        create_user(username="student2", role=Profile.ROLE_STUDENT)
        self.client.login(username="student2", password="pass12345")
        self.client.get(reverse("logout"))
        self.assertIn("_auth_user_id", self.client.session)
