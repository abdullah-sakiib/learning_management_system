from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Course(models.Model):
    ENROLLMENT_OPEN = "open"
    ENROLLMENT_APPROVAL = "approval"

    ENROLLMENT_TYPE_CHOICES = [
        (ENROLLMENT_OPEN, "Open Enrollment"),
        (ENROLLMENT_APPROVAL, "Approval Required"),
    ]

    LEVEL_BEGINNER = "Beginner"
    LEVEL_INTERMEDIATE = "Intermediate"
    LEVEL_ADVANCED = "Advanced"

    LEVEL_CHOICES = [
        (LEVEL_BEGINNER, "Beginner"),
        (LEVEL_INTERMEDIATE, "Intermediate"),
        (LEVEL_ADVANCED, "Advanced"),
    ]

    title = models.CharField(max_length=200)
    short_description = models.CharField(max_length=280, blank=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=80, blank=True)
    tags = models.CharField(max_length=280, blank=True)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default=LEVEL_BEGINNER)
    duration_weeks = models.PositiveIntegerField(default=12)
    lecture_count = models.PositiveIntegerField(default=10)
    assignment_count = models.PositiveIntegerField(default=0)
    quiz_count = models.PositiveIntegerField(default=0)
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(5)],
    )
    thumbnail = models.ImageField(upload_to="course_thumbnails/", blank=True, null=True)
    intro_video = models.FileField(upload_to="course_intro_videos/", blank=True, null=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses_taught",
    )
    enrollment_type = models.CharField(
        max_length=20,
        choices=ENROLLMENT_TYPE_CHOICES,
        default=ENROLLMENT_OPEN,
    )
    max_students = models.PositiveIntegerField(blank=True, null=True)
    allow_discussions = models.BooleanField(default=True)
    is_ended = models.BooleanField(default=False)
    ended_at = models.DateTimeField(blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    @property
    def tag_list(self):
        return [tag.strip() for tag in self.tags.split(",") if tag.strip()]

    @property
    def approved_enrollment_count(self):
        return self.enrollments.filter(status=Enrollment.STATUS_APPROVED).count()

    def is_at_capacity(self):
        if not self.max_students:
            return False
        return self.approved_enrollment_count >= self.max_students


class Enrollment(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    progress = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_APPROVED)
    approved_at = models.DateTimeField(blank=True, null=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "course")
        ordering = ["-enrolled_at"]

    def __str__(self):
        return f"{self.student.username} -> {self.course.title}"


class CourseDiscussionPost(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="discussion_posts",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_discussion_posts",
    )
    message = models.TextField(max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course.title}: {self.author.username}"


class CourseModule(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="modules",
    )
    title = models.CharField(max_length=200)
    overview = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class ModuleResource(models.Model):
    TYPE_VIDEO = "video"
    TYPE_FILE = "file"
    TYPE_LINK = "link"

    RESOURCE_TYPE_CHOICES = [
        (TYPE_VIDEO, "Video"),
        (TYPE_FILE, "File"),
        (TYPE_LINK, "External Link"),
    ]

    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name="resources",
    )
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES, default=TYPE_FILE)
    video_file = models.FileField(upload_to="module_videos/%Y/%m/%d/", blank=True, null=True)
    file = models.FileField(upload_to="module_files/%Y/%m/%d/", blank=True, null=True)
    external_url = models.URLField(blank=True)
    duration_minutes = models.PositiveIntegerField(blank=True, null=True)
    order = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.module.title} - {self.title}"


class ModuleCompletion(models.Model):
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="module_completions",
    )
    module = models.ForeignKey(
        CourseModule,
        on_delete=models.CASCADE,
        related_name="completions",
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("enrollment", "module")
        ordering = ["-completed_at"]

    def __str__(self):
        return f"{self.enrollment.student.username} completed {self.module.title}"


class CourseReview(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_reviews",
    )
    course_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    instructor_rating = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        unique_together = ("course", "student")

    def __str__(self):
        return f"{self.student.username} review for {self.course.title}"
