from django.conf import settings
from django.db import models


class Profile(models.Model):
    ROLE_STUDENT = "student"
    ROLE_INSTRUCTOR = "instructor"
    ROLE_ADMIN = "admin"

    ROLE_CHOICES = [
        (ROLE_STUDENT, "Student"),
        (ROLE_INSTRUCTOR, "Instructor"),
        (ROLE_ADMIN, "Admin"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_STUDENT,
    )
    department = models.CharField(max_length=120, blank=True)
    teacher_id = models.CharField(max_length=40, blank=True)
    university = models.CharField(max_length=180, blank=True)
    designation = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=120, blank=True)
    country = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Ensure instructor profiles always have a generated teacher ID.
        if self.role == self.ROLE_INSTRUCTOR and not self.teacher_id and self.user_id:
            self.teacher_id = f"TCH-{self.user_id:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        full_name = self.user.get_full_name().strip()
        name = full_name if full_name else self.user.username
        return f"{name} ({self.role})"
