from django.urls import path

from ..views import courses


urlpatterns = [
    path("courses/", courses.course_catalog, name="courses"),
    path("student/courses/", courses.student_course_catalog, name="student_courses"),
    path("courses/<int:course_id>/", courses.course_detail, name="course_detail"),
    path("courses/<int:course_id>/content/", courses.course_content, name="course_content"),
    path("courses/<int:course_id>/discussion/", courses.course_discussion, name="course_discussion"),
    path("courses/<int:course_id>/certificate/", courses.course_certificate_download, name="course_certificate_download"),
    path("courses/<int:course_id>/review/", courses.course_submit_review, name="course_submit_review"),
    path("courses/<int:course_id>/enroll/", courses.course_enroll, name="course_enroll"),
    path("courses/<int:course_id>/unenroll/", courses.course_unenroll, name="course_unenroll"),
]
