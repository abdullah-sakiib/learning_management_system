from django.urls import path

from ..views import dashboards


urlpatterns = [
    path("dashboard/student/", dashboards.student_dashboard, name="student_dashboard"),
    path("dashboard/instructor/", dashboards.instructor_dashboard, name="instructor_dashboard"),
    path("dashboard/admin/", dashboards.admin_dashboard, name="admin_dashboard"),
]
