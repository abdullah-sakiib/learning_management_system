from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

# Create your models here.


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


class Assignment(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    attachment = models.FileField(upload_to="assignment_attachments/%Y/%m/%d/", blank=True, null=True)
    due_date = models.DateTimeField(blank=True, null=True)
    publish_at = models.DateTimeField(blank=True, null=True)
    max_score = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)])
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assignments_created",
    )
    is_published = models.BooleanField(default=True)
    archived_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class Submission(models.Model):
    STATUS_SUBMITTED = "submitted"
    STATUS_GRADED = "graded"
    STATUS_LATE = "late"

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_GRADED, "Graded"),
        (STATUS_LATE, "Late"),
    ]

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    file = models.FileField(upload_to="assignment_submissions/%Y/%m/%d/")
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_SUBMITTED)
    score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    feedback = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-submitted_at"]
        unique_together = ("assignment", "student")

    def __str__(self):
        return f"{self.student.username} - {self.assignment.title}"


class Quiz(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="quizzes",
    )
    title = models.CharField(max_length=200)
    total_marks = models.PositiveIntegerField(default=100, validators=[MinValueValidator(1)])
    time_limit_minutes = models.PositiveIntegerField(default=30, validators=[MinValueValidator(1)])
    is_published = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quizzes_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course.title}: {self.title}"


class QuizQuestion(models.Model):
    TYPE_MCQ = "mcq"
    TYPE_TRUE_FALSE = "true_false"
    TYPE_TEXT = "text"

    QUESTION_TYPE_CHOICES = [
        (TYPE_MCQ, "Multiple Choice"),
        (TYPE_TRUE_FALSE, "True/False"),
        (TYPE_TEXT, "Text"),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    question_text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE_CHOICES, default=TYPE_MCQ)
    options_json = models.JSONField(blank=True, null=True)
    correct_answer = models.TextField(blank=True)
    marks = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.quiz.title} - Q{self.order}"


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quiz_attempts",
    )
    score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-started_at"]
        unique_together = ("quiz", "student")

    def __str__(self):
        return f"{self.student.username} - {self.quiz.title}"


class QuizResponse(models.Model):
    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    question = models.ForeignKey(
        QuizQuestion,
        on_delete=models.CASCADE,
        related_name="responses",
    )
    answer_text = models.TextField(blank=True)
    is_correct = models.BooleanField(default=False)
    awarded_marks = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = ("attempt", "question")

    def __str__(self):
        return f"Attempt {self.attempt_id} - Question {self.question_id}"


class Announcement(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="announcements",
        blank=True,
        null=True,
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="announcements_authored",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_global = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


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