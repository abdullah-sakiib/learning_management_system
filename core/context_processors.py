from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import Announcement, Course, Enrollment, Profile


def user_role_context(request):
    if not request.user.is_authenticated:
        return {
            "current_user_role": None,
            "is_student": False,
            "is_instructor": False,
            "is_admin": False,
            "current_user_name": "Guest",
            "current_user_email": "",
            "topbar_search_placeholder": "Search...",
            "topbar_notifications": [],
            "show_topbar_notifications": False,
            "topbar_course_search_url": "",
        }

    try:
        role = request.user.profile.role
    except Profile.DoesNotExist:
        role = Profile.ROLE_ADMIN if request.user.is_staff else Profile.ROLE_STUDENT

    full_name = request.user.get_full_name().strip()
    display_name = full_name if full_name else request.user.username

    if role == Profile.ROLE_INSTRUCTOR:
        search_placeholder = "Search courses, submissions, students..."
        notifications = []
    elif role == Profile.ROLE_ADMIN:
        search_placeholder = "Search users, courses, reports..."
        notifications = [
            {
                "icon": "ri-alert-line",
                "icon_wrap_class": "bg-amber-100",
                "icon_class": "text-amber-500",
                "title": "Email service is degraded",
                "subtitle": "System status monitor",
                "time": "15 mins ago",
            },
            {
                "icon": "ri-user-add-line",
                "icon_wrap_class": "bg-primary-100",
                "icon_class": "text-primary-600",
                "title": "24 new users this week",
                "subtitle": "Students + instructors",
                "time": "Today",
            },
            {
                "icon": "ri-shield-check-line",
                "icon_wrap_class": "bg-emerald-100",
                "icon_class": "text-emerald-500",
                "title": "Backup completed successfully",
                "subtitle": "Nightly job",
                "time": "Last night",
            },
        ]
    else:
        search_placeholder = "Search courses, assignments..."
        notifications = [
            {
                "icon": "ri-file-list-3-line",
                "icon_wrap_class": "bg-primary-100",
                "icon_class": "text-primary-600",
                "title": "New assignment posted",
                "subtitle": "Check your enrolled courses",
                "time": "2 hours ago",
            },
            {
                "icon": "ri-checkbox-circle-line",
                "icon_wrap_class": "bg-emerald-100",
                "icon_class": "text-emerald-500",
                "title": "Assignment graded",
                "subtitle": "Open Grades to view your score",
                "time": "5 hours ago",
            },
            {
                "icon": "ri-time-line",
                "icon_wrap_class": "bg-amber-100",
                "icon_class": "text-amber-500",
                "title": "Quiz deadline tomorrow",
                "subtitle": "Review your upcoming quiz deadlines",
                "time": "1 day ago",
            },
        ]

    if role == Profile.ROLE_STUDENT:
        course_ids = Enrollment.objects.filter(
            student=request.user,
            status=Enrollment.STATUS_APPROVED,
        ).values_list("course_id", flat=True)
        announcement_qs = Announcement.objects.filter(Q(is_global=True) | Q(course_id__in=course_ids))
    elif role == Profile.ROLE_INSTRUCTOR:
        course_ids = Course.objects.filter(instructor=request.user).values_list("id", flat=True)
        announcement_qs = Announcement.objects.filter(Q(is_global=True) | Q(course_id__in=course_ids))
    else:
        announcement_qs = Announcement.objects.all()

    announcement_notifications = []
    if role == Profile.ROLE_STUDENT:
        for announcement in announcement_qs.select_related("course").order_by("-created_at")[:3]:
            scope = "Global" if announcement.is_global else (announcement.course.title if announcement.course else "General")
            age_seconds = max(0, int((timezone.now() - announcement.created_at).total_seconds()))
            if age_seconds < 3600:
                age_label = f"{max(1, age_seconds // 60)} mins ago"
            elif age_seconds < 86400:
                age_label = f"{age_seconds // 3600} hours ago"
            else:
                age_label = f"{age_seconds // 86400} days ago"

            announcement_notifications.append(
                {
                    "icon": "ri-megaphone-line",
                    "icon_wrap_class": "bg-violet-100",
                    "icon_class": "text-violet-600",
                    "title": announcement.title,
                    "subtitle": scope,
                    "time": age_label,
                    "url": reverse("announcements"),
                }
            )

    notifications = announcement_notifications + notifications
    notifications = notifications[:6]

    return {
        "current_user_role": role,
        "is_student": role == Profile.ROLE_STUDENT,
        "is_instructor": role == Profile.ROLE_INSTRUCTOR,
        "is_admin": role == Profile.ROLE_ADMIN,
        "current_user_name": display_name,
        "current_user_email": request.user.email,
        "topbar_search_placeholder": search_placeholder,
        "topbar_notifications": notifications,
        "show_topbar_notifications": role == Profile.ROLE_STUDENT,
        "topbar_course_search_url": reverse("student_courses") if role == Profile.ROLE_STUDENT else "",
    }
