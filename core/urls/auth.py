from django.urls import path

from ..views import auth


urlpatterns = [
    path("", auth.landing, name="landing"),
    path("login/", auth.login_page, name="login"),
    path("logout/", auth.logout_page, name="logout"),
    path("register/", auth.register_page, name="register"),
    path("password-reset/", auth.password_reset_page, name="password_reset"),
    path("dashboard/", auth.dashboard, name="dashboard"),
]
