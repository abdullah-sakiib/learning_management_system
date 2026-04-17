from django.contrib import admin
from .models import (
    Announcement,
    Assignment,
    CourseDiscussionPost,
    CourseModule,
    Course,
    Enrollment,
    ModuleResource,
    Profile,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    QuizResponse,
    Submission,
)

# Register your models here.
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "created_at")
    list_filter = ("role", "department")
    search_fields = ("user__username", "user__email", "department")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "level",
        "instructor",
        "enrollment_type",
        "max_students",
        "allow_discussions",
        "is_published",
        "updated_at",
    )
    list_filter = ("category", "level", "enrollment_type", "allow_discussions", "is_published")
    search_fields = ("title", "category", "instructor__username", "instructor__email")


@admin.register(CourseModule)
class CourseModuleAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "order", "is_published", "created_at")
    list_filter = ("is_published", "course")
    search_fields = ("title", "course__title")


@admin.register(ModuleResource)
class ModuleResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "module", "resource_type", "order", "is_published", "created_at")
    list_filter = ("resource_type", "is_published", "module__course")
    search_fields = ("title", "module__title", "module__course__title")


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "status", "progress", "enrolled_at", "approved_at")
    list_filter = ("course", "status")
    search_fields = ("student__username", "student__email", "course__title")


@admin.register(CourseDiscussionPost)
class CourseDiscussionPostAdmin(admin.ModelAdmin):
    list_display = ("course", "author", "created_at", "updated_at")
    list_filter = ("course",)
    search_fields = ("course__title", "author__username", "author__email", "message")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "max_score", "is_published", "created_at")
    list_filter = ("is_published", "course")
    search_fields = ("title", "course__title", "created_by__username")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "status", "score", "submitted_at")
    list_filter = ("status", "assignment__course")
    search_fields = ("assignment__title", "student__username", "student__email")


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "total_marks", "time_limit_minutes", "is_published")
    list_filter = ("is_published", "course")
    search_fields = ("title", "course__title", "created_by__username")


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ("quiz", "order", "question_type", "marks")
    list_filter = ("question_type", "quiz")
    search_fields = ("quiz__title", "question_text")


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("quiz", "student", "score", "started_at", "submitted_at")
    list_filter = ("quiz",)
    search_fields = ("quiz__title", "student__username", "student__email")


@admin.register(QuizResponse)
class QuizResponseAdmin(admin.ModelAdmin):
    list_display = ("attempt", "question", "is_correct", "awarded_marks")
    list_filter = ("is_correct", "question__quiz")
    search_fields = ("attempt__student__username", "question__question_text")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "is_global", "author", "created_at")
    list_filter = ("is_global", "course")
    search_fields = ("title", "body", "author__username")