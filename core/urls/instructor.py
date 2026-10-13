from django.urls import path

from ..views import instructor


urlpatterns = [
    path("instructor/courses/", instructor.instructor_my_courses, name="instructor_my_courses"),
    path("instructor/create-course/", instructor.instructor_create_course, name="instructor_create_course"),
    path("instructor/submissions/", instructor.instructor_submissions, name="instructor_submissions"),
    path("instructor/course/<int:course_id>/content/", instructor.instructor_manage_content, name="instructor_manage_content"),
    path("instructor/quiz/<int:quiz_id>/edit/", instructor.instructor_edit_quiz, name="instructor_edit_quiz"),
    path("instructor/quiz/<int:quiz_id>/attempts/", instructor.instructor_quiz_attempts, name="instructor_quiz_attempts"),
]
