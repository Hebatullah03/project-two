import json
import logging
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from core.services import patient_service, session_service, alert_service
from core.models import Alert, Doctor,Patient, Session

logger = logging.getLogger(__name__)


def _require_auth(request):
    if not request.user.is_authenticated:
        return redirect("core:login")
    return None


def receptionist_dashboard(request):
    guard = _require_auth(request)
    if guard:
        return guard
    return render(request, "receptionist/dashboard.html", {
        "total_patients":   Patient.objects.count(),
        "today_sessions":   Session.objects.filter(start_time__date=timezone.now().date()).count(),
        "active_alerts":    Alert.objects.filter(status="triggered").count(),
        "waiting_sessions": Session.objects.filter(status="scheduled").count(),
        "upcoming_sessions": (
            Session.objects.select_related("patient__user")
            .filter(start_time__gte=timezone.now())
            .order_by("start_time")[:5]
        ),
    })


def receptionist_patients(request):
    guard = _require_auth(request)
    if guard:
        return guard
    if request.method == "POST":
        return _save_patient_view(request)
    return _list_patients_view(request)


def _list_patients_view(request):
    search      = request.GET.get("search", "")
    sort        = request.GET.get("sort", "-id")
    page_number = request.GET.get("page", 1)

    patients = Patient.objects.select_related("user", "doctor__employee__user")
    patients = patient_service.search_patients(patients, search)

    sort_map = {
        "name_asc":  ("user__first_name", "user__last_name"),
        "name_desc": ("-user__first_name", "-user__last_name"),
        "oldest":    ("id",),
    }
    patients = patients.order_by(*sort_map.get(sort, ("-id",)))

    paginator = Paginator(patients, 10)
    page_obj  = paginator.get_page(page_number)

    return render(request, "receptionist/patients.html", {
        "patients": page_obj,
        "doctors":  Doctor.objects.select_related("employee__user"),
        "search":   search,
        "sort":     sort,
    })


def _save_patient_view(request):
    patient_id = request.POST.get("patient_id")
    data = dict(
        first_name=request.POST.get("first_name"),
        last_name=request.POST.get("last_name"),
        email=request.POST.get("email"),
        phone=request.POST.get("phone"),
        gender=request.POST.get("gender"),
        date_of_birth=request.POST.get("date_of_birth"),
        doctor_id=request.POST.get("doctor_id") or None,
        face_image=request.FILES.get("face_image"),
    )

    try:
        if patient_id:
            patient_service.update_patient(patient_id=patient_id, **data)
            messages.success(request, "Patient updated successfully.")
        else:
            patient_service.create_patient(**data)
            messages.success(request, "Patient created successfully.")
    except ValueError as exc:
        messages.error(request, str(exc))
    except IntegrityError:
        messages.error(request, "A patient with this email already exists.")
    except Exception:
        messages.error(request, "Something went wrong.")

    return redirect("core:receptionist_patients")


def receptionist_sessions(request):
    guard = _require_auth(request)
    if guard:
        return guard
    if request.method == "POST":
        return _create_or_update_session_view(request)
    return _list_sessions_view(request)


def _list_sessions_view(request):
    sessions     = Session.objects.select_related("patient__user", "doctor__employee__user")
    search_query = request.GET.get("search", "")
    sessions     = session_service.search_sessions(sessions, search_query)

    sort_by  = request.GET.get("sort", "-start_time")
    sessions = sessions.order_by(sort_by)

    paginator = Paginator(sessions, 10)
    page_obj  = paginator.get_page(request.GET.get("page"))

    return render(request, "receptionist/sessions.html", {
        "sessions":     page_obj,
        "search_query": search_query,
        "sort_by":      sort_by,
        "stats":        session_service.get_session_stats(),
        "patients":     Patient.objects.select_related("user").all(),
        "doctors":      Doctor.objects.select_related("employee__user").all(),
    })


def _create_or_update_session_view(request):
    session_id = request.POST.get("session_id")
    try:
        if session_id:
            session_service.update_session(
                session_id=session_id,
                patient_id=request.POST.get("patient"),
                doctor_id=request.POST.get("doctor"),
                date_str=request.POST.get("date"),
                time_str=request.POST.get("time"),
            )
            messages.success(request, "Session updated successfully.")
        else:
            session_service.create_session(
                patient_id=request.POST.get("patient"),
                doctor_id=request.POST.get("doctor"),
                date_str=request.POST.get("date"),
                time_str=request.POST.get("time"),
            )
            messages.success(request, "Session created successfully.")
    except ValueError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        logger.error("Error creating/updating session: %s", exc)
        messages.error(request, "Something went wrong.")

    return redirect("core:receptionist_sessions")


@require_POST
def cancel_session(request, session_id):
    guard = _require_auth(request)
    if guard:
        return guard
    try:
        session_service.cancel_session(session_id)
        messages.success(request, "Session cancelled successfully.")
    except ValueError as exc:
        messages.info(request, str(exc))
    except Exception:
        messages.error(request, "Something went wrong while cancelling the session.")

    return redirect("core:receptionist_sessions")


def receptionist_profile(request):
    guard = _require_auth(request)
    if guard:
        return guard
    return render(request, "receptionist/profile.html", {"profile_user": request.user})


def receptionist_alerts(request):
    guard = _require_auth(request)
    if guard:
        return guard

    alerts = alert_service.get_all_alerts()
    counts = alert_service.get_alert_counts(alerts)

    return render(request, "receptionist/alerts.html", {"alerts": alerts, **counts, "Alert": Alert})


def update_alert_status(request, alert_id):
    guard = _require_auth(request)
    if guard:
        return guard

    if request.method == "POST":
        try:
            alert_service.update_alert_status(alert_id, request.POST.get("status"), request.user)
            messages.success(request, "Alert status updated.")
        except PermissionDenied as exc:
            messages.error(request, str(exc))
        except ValueError as exc:
            messages.error(request, str(exc))

    return redirect(request.META.get("HTTP_REFERER", "core:home"))
