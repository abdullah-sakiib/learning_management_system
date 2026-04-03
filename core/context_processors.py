from .models import Profile


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
        }

    try:
        role = request.user.profile.role
    except Profile.DoesNotExist:
        role = Profile.ROLE_ADMIN if request.user.is_staff else Profile.ROLE_STUDENT

    full_name = request.user.get_full_name().strip()
    display_name = full_name if full_name else request.user.username

    if role == Profile.ROLE_INSTRUCTOR:
        search_placeholder = "Search courses, submissions, students..."
        notifications = [
            {
                "icon": "ri-file-check-line",
                "icon_wrap_class": "bg-amber-100",
                "icon_class": "text-amber-500",
                "title": "3 submissions need grading",
                "subtitle": "Algorithms 101 · Database",
                "time": "1 hour ago",
            },
            {
                "icon": "ri-user-add-line",
                "icon_wrap_class": "bg-primary-100",
                "icon_class": "text-primary-600",
                "title": "12 new enrollments this week",
                "subtitle": "Across your active courses",
                "time": "Today",
            },
            {
                "icon": "ri-megaphone-line",
                "icon_wrap_class": "bg-violet-100",
                "icon_class": "text-violet-600",
                "title": "Reminder to publish Week 5",
                "subtitle": "Computer Networks",
                "time": "Tomorrow",
            },
        ]
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
                "subtitle": "Week 4 · Algorithms 101",
                "time": "2 hours ago",
            },
            {
                "icon": "ri-checkbox-circle-line",
                "icon_wrap_class": "bg-emerald-100",
                "icon_class": "text-emerald-500",
                "title": "Assignment graded",
                "subtitle": "Score: 92/100 · Database",
                "time": "5 hours ago",
            },
            {
                "icon": "ri-time-line",
                "icon_wrap_class": "bg-amber-100",
                "icon_class": "text-amber-500",
                "title": "Quiz deadline tomorrow",
                "subtitle": "Algorithms 101 · Quiz #3",
                "time": "1 day ago",
            },
        ]

    return {
        "current_user_role": role,
        "is_student": role == Profile.ROLE_STUDENT,
        "is_instructor": role == Profile.ROLE_INSTRUCTOR,
        "is_admin": role == Profile.ROLE_ADMIN,
        "current_user_name": display_name,
        "current_user_email": request.user.email,
        "topbar_search_placeholder": search_placeholder,
        "topbar_notifications": notifications,
    }
