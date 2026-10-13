from django.urls import path

from ..views import profile


urlpatterns = [
    path("settings/", profile.settings_page, name="settings"),
    path("profile/", profile.profile_page, name="profile"),
    path("profile/announcements/", profile.announcements, name="announcements"),
]
