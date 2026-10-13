from django.urls import include, path


urlpatterns = [
    path("", include("core.urls.auth")),
    path("", include("core.urls.courses")),
    path("", include("core.urls.assessments")),
    path("", include("core.urls.dashboards")),
    path("", include("core.urls.instructor")),
    path("", include("core.urls.profile")),
]
