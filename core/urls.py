# from django.urls import path
# from . import views

# urlpatterns = [
# path('', views.landing, name='landing'),

# path('login/', views.login_page, name='login'),
# path('register/', views.register_page, name='register'),

# path('courses/', views.course_catalog, name='courses'),
# path("courses/int:course_id/", views.course_detail, name="course_detail"),
# path("courses/int:course_id/content/", views.course_content, name="course_content"),

# path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
# path('dashboard/instructor/', views.instructor_dashboard, name='instructor_dashboard'),
# path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),

# path('profile/', views.profile_page, name='profile'),
# path('profile/announcements/', views.announcements, name='announcements'),

# path("password-reset/", views.password_reset_page, name="password_reset"),
# ]

from django.urls import path
from . import views

urlpatterns = [
    path("", views.landing, name="landing"),

    path("login/", views.login_page, name="login"),
    path("logout/", views.logout_page, name="logout"),
    path("register/", views.register_page, name="register"),
    path("password-reset/", views.password_reset_page, name="password_reset"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/student/", views.student_dashboard, name="student_dashboard"),
    path("dashboard/instructor/", views.instructor_dashboard, name="instructor_dashboard"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),

    path("courses/", views.course_catalog, name="courses"),
    path("student/courses/", views.student_course_catalog, name="student_courses"),
    path("instructor/courses/", views.instructor_my_courses, name="instructor_my_courses"),
    path("courses/<int:course_id>/", views.course_detail, name="course_detail"),
    path("courses/<int:course_id>/content/", views.course_content, name="course_content"),
    path("courses/<int:course_id>/discussion/", views.course_discussion, name="course_discussion"),
    path("courses/<int:course_id>/review/", views.course_submit_review, name="course_submit_review"),
    path("courses/<int:course_id>/enroll/", views.course_enroll, name="course_enroll"),
    path("courses/<int:course_id>/unenroll/", views.course_unenroll, name="course_unenroll"),

    path("assignments/", views.assignments, name="assignments"),
    path("grades/", views.grades, name="grades"),
    path("quiz/", views.quiz, name="quiz"),
    path("quiz/<int:quiz_id>/take/", views.quiz_take, name="quiz_take"),
    path("settings/", views.settings_page, name="settings"),

    path("profile/", views.profile_page, name="profile"),
    path("profile/announcements/", views.announcements, name="announcements"),

    path("instructor/create-course/", views.instructor_create_course, name="instructor_create_course"),
    path("instructor/submissions/", views.instructor_submissions, name="instructor_submissions"),
    path("instructor/course/<int:course_id>/content/", views.instructor_manage_content, name="instructor_manage_content"),
    path("instructor/quiz/<int:quiz_id>/edit/", views.instructor_edit_quiz, name="instructor_edit_quiz"),
    path("instructor/quiz/<int:quiz_id>/attempts/", views.instructor_quiz_attempts, name="instructor_quiz_attempts"),
]