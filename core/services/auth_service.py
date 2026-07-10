from django.contrib.auth import authenticate as django_authenticate
from django.contrib.auth import login as django_login
from django.contrib.auth import logout as django_logout
from django.contrib.auth import update_session_auth_hash
from core.models import User


def login_user(request, email: str, password: str) -> User:
    user = django_authenticate(request, username=email, password=password)
    if user is None:
        raise ValueError("Invalid email or password.")
    django_login(request, user)
    return user


def logout_user(request) -> None:
    django_logout(request)


def get_user_role(user: User) -> str | None:
    if user.groups.filter(name=User.Role.DOCTOR).exists():
        return User.Role.DOCTOR
    if user.groups.filter(name=User.Role.RECEPTIONIST).exists():
        return User.Role.RECEPTIONIST
    return None


def get_redirect_url_for_role(role: str | None) -> str:
    return {
        User.Role.DOCTOR: '/doctor/patients/',
        User.Role.RECEPTIONIST: '/receptionist/dashboard/',
    }.get(role, '/')


def change_password(request, current_password: str, new_password: str, confirm_password: str) -> None:
    if not all([current_password, new_password, confirm_password]):
        raise ValueError("All password fields are required.")
    if not request.user.check_password(current_password):
        raise ValueError("Current password is incorrect.")
    if new_password != confirm_password:
        raise ValueError("New password and confirmation do not match.")

    request.user.set_password(new_password)
    request.user.save()
    update_session_auth_hash(request, request.user)


def update_profile(user: User, first_name: str, last_name: str, phone: str) -> User:
    user.first_name = first_name.strip()
    user.last_name = last_name.strip()
    user.phone = phone.strip() or None
    user.save()
    return user
