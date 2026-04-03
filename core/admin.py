from django.contrib import admin
from .models import Course, Enrollment, Profile

# Register your models here.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "created_at")
    list_filter = ("role", "department")
    search_fields = ("user__username", "user__email", "department")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "level", "instructor", "is_published", "updated_at")
    list_filter = ("category", "level", "is_published")
    search_fields = ("title", "category", "instructor__username", "instructor__email")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "progress", "enrolled_at")
    list_filter = ("course",)
    search_fields = ("student__username", "student__email", "course__title")