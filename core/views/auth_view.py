import logging
from django.contrib import messages
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from core.services import auth_service
from core.models import User

logger = logging.getLogger(__name__)





def _require_auth(request):
    if not request.user.is_authenticated:
        return redirect("core:login")
    return None



def home(request):
    if not request.user.is_authenticated:
        return redirect("/auth/login/")
    role = auth_service.get_user_role(request.user)
    return redirect(auth_service.get_redirect_url_for_role(role))


def login_view(request):
    if request.method == "GET":
        return render(request, "auth/login.html")

    try:
        user = auth_service.login_user(
            request,
            email=request.POST.get("email", ""),
            password=request.POST.get("password", ""),
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return render(request, "auth/login.html")

    return redirect(auth_service.get_redirect_url_for_role(auth_service.get_user_role(user)))


def logout_view(request):
    auth_service.logout_user(request)
    return redirect("/auth/login/")


@require_POST
def update_profile(request):
    guard = _require_auth(request)
    if guard:
        return guard

    try:
        auth_service.update_profile(
            request.user,
            first_name=request.POST.get("first_name", ""),
            last_name=request.POST.get("last_name", ""),
            phone=request.POST.get("phone", ""),
        )
        messages.success(request, "Profile updated successfully.")
    except Exception:
        messages.error(request, "Unable to update profile.")

    role = auth_service.get_user_role(request.user)
    if role == User.Role.DOCTOR:
        return redirect("core:doctor_profile")
    return redirect("core:receptionist_profile")


@require_POST
def change_password(request):
    guard = _require_auth(request)
    if guard:
        return guard

    role = auth_service.get_user_role(request.user)
    profile_page = {
        User.Role.DOCTOR: "core:doctor_profile",
        User.Role.RECEPTIONIST: "core:receptionist_profile",
    }

    try:
        auth_service.change_password(
            request,
            current_password=request.POST.get("current_password", ""),
            new_password=request.POST.get("new_password", ""),
            confirm_password=request.POST.get("confirm_password", ""),
        )
        messages.success(request, "Password changed successfully.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect(profile_page.get(role, "core:login"))

