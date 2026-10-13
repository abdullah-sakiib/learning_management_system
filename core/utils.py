def get_display_name(user):
    full_name = user.get_full_name().strip()
    return full_name if full_name else user.username


def build_teacher_id(user_id):
    return f"TCH-{user_id:05d}"
