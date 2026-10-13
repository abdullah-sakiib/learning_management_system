from django.utils import timezone

from ..models import Enrollment


def approve_enrollment(enrollment):
    """Approve an enrollment while enforcing course capacity."""
    if enrollment.status == Enrollment.STATUS_APPROVED:
        return False
    if enrollment.course.is_at_capacity():
        raise ValueError("Course is already at maximum capacity.")
    enrollment.status = Enrollment.STATUS_APPROVED
    enrollment.approved_at = timezone.now()
    enrollment.save(update_fields=["status", "approved_at"])
    return True


def remove_enrollment(enrollment):
    enrollment.delete()
