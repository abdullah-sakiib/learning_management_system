import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from core.forms.accounts import ProfileGeneralForm, RegistrationForm
from core.models import Profile
from core.permissions import get_user_role
from core.utils import build_teacher_id, get_display_name


pytestmark = [pytest.mark.django_db, pytest.mark.member_a]


PROFILE_BOUNDARIES = [
    pytest.param("first_name", 0, True, id="A-TC-001-first-name-empty"),
    pytest.param("first_name", 1, True, id="A-TC-002-first-name-min"),
    pytest.param("first_name", 149, True, id="A-TC-003-first-name-below-max"),
    pytest.param("first_name", 150, True, id="A-TC-004-first-name-max"),
    pytest.param("first_name", 151, False, id="A-TC-005-first-name-above-max"),
    pytest.param("last_name", 0, True, id="A-TC-006-last-name-empty"),
    pytest.param("last_name", 1, True, id="A-TC-007-last-name-min"),
    pytest.param("last_name", 149, True, id="A-TC-008-last-name-below-max"),
    pytest.param("last_name", 150, True, id="A-TC-009-last-name-max"),
    pytest.param("last_name", 151, False, id="A-TC-010-last-name-above-max"),
    pytest.param("phone", 0, True, id="A-TC-011-phone-empty"),
    pytest.param("phone", 1, True, id="A-TC-012-phone-min"),
    pytest.param("phone", 29, True, id="A-TC-013-phone-below-max"),
    pytest.param("phone", 30, True, id="A-TC-014-phone-max"),
    pytest.param("phone", 31, False, id="A-TC-015-phone-above-max"),
    pytest.param("bio", 0, True, id="A-TC-016-bio-empty"),
    pytest.param("bio", 1, True, id="A-TC-017-bio-min"),
    pytest.param("bio", 499, True, id="A-TC-018-bio-below-max"),
    pytest.param("bio", 500, True, id="A-TC-019-bio-max"),
    pytest.param("bio", 501, False, id="A-TC-020-bio-above-max"),
]


@pytest.mark.unit
@pytest.mark.bva
@pytest.mark.parametrize(("field", "length", "expected"), PROFILE_BOUNDARIES)
def test_profile_general_form_boundaries(student, field, length, expected):
    data = {
        "first_name": "Test",
        "last_name": "Student",
        "email": student.email,
        "phone": "123",
        "city": "Dhaka",
        "country": "Bangladesh",
        "bio": "Profile",
    }
    data[field] = "x" * length

    form = ProfileGeneralForm(data=data, user=student)

    assert form.is_valid() is expected


REGISTRATION_CLASSES = [
    pytest.param({}, True, id="A-TC-021-valid-student-registration"),
    pytest.param({"role": Profile.ROLE_INSTRUCTOR}, True, id="A-TC-022-valid-instructor-registration"),
    pytest.param({"first_name": ""}, False, id="A-TC-023-missing-first-name"),
    pytest.param({"email": "not-an-email"}, False, id="A-TC-024-invalid-email-class"),
    pytest.param({"password2": "Different934!"}, False, id="A-TC-025-password-mismatch-class"),
    pytest.param({"terms": False}, False, id="A-TC-026-terms-not-accepted"),
    pytest.param({"role": Profile.ROLE_ADMIN}, False, id="A-TC-027-unsupported-role-class"),
    pytest.param({"password1": "short", "password2": "short"}, False, id="A-TC-028-weak-password-class"),
]


@pytest.mark.unit
@pytest.mark.equivalence
@pytest.mark.parametrize(("changes", "expected"), REGISTRATION_CLASSES)
def test_registration_equivalence_classes(valid_registration_data, changes, expected):
    data = {**valid_registration_data, **changes}
    form = RegistrationForm(data=data)
    assert form.is_valid() is expected


ROLE_CASES = [
    pytest.param(Profile.ROLE_STUDENT, False, Profile.ROLE_STUDENT, id="A-TC-029-student-profile-role"),
    pytest.param(Profile.ROLE_INSTRUCTOR, False, Profile.ROLE_INSTRUCTOR, id="A-TC-030-instructor-profile-role"),
    pytest.param(Profile.ROLE_ADMIN, True, Profile.ROLE_ADMIN, id="A-TC-031-admin-profile-role"),
    pytest.param(None, True, Profile.ROLE_ADMIN, id="A-TC-032-staff-without-profile"),
]


@pytest.mark.unit
@pytest.mark.decision_table
@pytest.mark.parametrize(("profile_role", "is_staff", "expected"), ROLE_CASES)
def test_get_user_role_decisions(django_user_model, profile_role, is_staff, expected):
    user = django_user_model.objects.create_user(
        username=f"role-{expected}-{profile_role or 'none'}",
        password="SafePass934!x",
        is_staff=is_staff,
    )
    if profile_role:
        Profile.objects.create(user=user, role=profile_role)
    assert get_user_role(user) == expected


DISPLAY_CASES = [
    pytest.param("Ada", "Lovelace", "username1", "Ada Lovelace", id="A-TC-033-full-display-name"),
    pytest.param("Ada", "", "username2", "Ada", id="A-TC-034-partial-display-name"),
    pytest.param("", "", "username3", "username3", id="A-TC-035-username-fallback"),
]


@pytest.mark.unit
@pytest.mark.parametrize(("first", "last", "username", "expected"), DISPLAY_CASES)
def test_display_name(django_user_model, first, last, username, expected):
    user = django_user_model(username=username, first_name=first, last_name=last)
    assert get_display_name(user) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("user_id", "expected"),
    [
        pytest.param(1, "TCH-00001", id="A-TC-036-first-teacher-id"),
        pytest.param(99999, "TCH-99999", id="A-TC-037-five-digit-teacher-id"),
    ],
)
def test_build_teacher_id(user_id, expected):
    assert build_teacher_id(user_id) == expected


LOGIN_CASES = [
    pytest.param("username", True, "student_dashboard", id="A-TC-038-login-by-username"),
    pytest.param("email", True, "student_dashboard", id="A-TC-039-login-by-email"),
    pytest.param("username", False, None, id="A-TC-040-wrong-password"),
    pytest.param("unknown", False, None, id="A-TC-041-unknown-identity"),
]


@pytest.mark.integration
@pytest.mark.basis_path
@pytest.mark.parametrize(("identity_kind", "valid_password", "redirect_name"), LOGIN_CASES)
def test_login_paths(client, student, identity_kind, valid_password, redirect_name):
    identity = {
        "username": student.username,
        "email": student.email,
        "unknown": "nobody@example.com",
    }[identity_kind]
    response = client.post(
        reverse("login"),
        {"email": identity, "password": "SafePass934!x" if valid_password else "wrong"},
    )
    if redirect_name:
        assert response.status_code == 302
        assert response.url == reverse(redirect_name)
    else:
        assert response.status_code == 200
        assert "_auth_user_id" not in client.session


@pytest.mark.integration
@pytest.mark.basis_path
def test_a_tc_042_authenticated_login_redirects_to_role_dashboard(client, student, login):
    login(student)
    response = client.get(reverse("login"))
    assert response.status_code == 302
    assert response.url == reverse("student_dashboard")


ACCESS_CASES = [
    pytest.param(None, "login", id="A-TC-043-anonymous-admin-access"),
    pytest.param(Profile.ROLE_STUDENT, "student_dashboard", id="A-TC-044-student-admin-access"),
    pytest.param(Profile.ROLE_INSTRUCTOR, "instructor_dashboard", id="A-TC-045-instructor-admin-access"),
    pytest.param(Profile.ROLE_ADMIN, None, id="A-TC-046-admin-admin-access"),
]


@pytest.mark.integration
@pytest.mark.decision_table
@pytest.mark.parametrize(("role", "redirect_name"), ACCESS_CASES)
def test_admin_dashboard_access_decision(client, user_factory, role, redirect_name):
    if role:
        user = user_factory(role=role, username=f"access-{role}", is_staff=role == Profile.ROLE_ADMIN)
        client.force_login(user)
    response = client.get(reverse("admin_dashboard"))
    if redirect_name:
        assert response.status_code == 302
        assert reverse(redirect_name) in response.url
    else:
        assert response.status_code == 200


ADMIN_ACTIONS = [
    pytest.param("deactivate_user", True, False, id="A-TC-047-deactivate-active-user"),
    pytest.param("deactivate_user", False, False, id="A-TC-048-deactivate-inactive-user"),
    pytest.param("activate_user", False, True, id="A-TC-049-activate-inactive-user"),
    pytest.param("activate_user", True, True, id="A-TC-050-activate-active-user"),
]


@pytest.mark.integration
@pytest.mark.basis_path
@pytest.mark.parametrize(("action", "initial_active", "expected_active"), ADMIN_ACTIONS)
def test_admin_user_management_paths(client, admin_user, user_factory, action, initial_active, expected_active):
    target = user_factory(role=Profile.ROLE_STUDENT, username=f"target-{action}-{initial_active}")
    target.is_active = initial_active
    target.save(update_fields=["is_active"])
    client.force_login(admin_user)

    response = client.post(reverse("admin_dashboard"), {"action": action, "user_id": target.id})

    assert response.status_code == 302
    target.refresh_from_db()
    assert target.is_active is expected_active

