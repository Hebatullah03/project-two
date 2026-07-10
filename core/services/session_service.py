from datetime import date, datetime
from django.utils import timezone
from core.models import Doctor, Session


def create_session(patient_id, doctor_id, date_str: str, time_str: str) -> Session:
    try:
        naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid date or time: {exc}") from exc

    return Session.objects.create(
        patient_id=patient_id,
        doctor_id=doctor_id,
        start_time=timezone.make_aware(naive),
        status=Session.Status.SCHEDULED,
    )


def update_session(session_id, patient_id, doctor_id, date_str: str, time_str: str) -> Session:
    try:
        naive = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Invalid date or time: {exc}") from exc

    session = Session.objects.get(id=session_id)
    session.patient_id = patient_id
    session.doctor_id = doctor_id
    session.start_time = timezone.make_aware(naive)
    session.save()
    return session


def cancel_session(session_id) -> Session:
    session = Session.objects.get(id=session_id)

    if session.status == Session.Status.CANCELLED:
        raise ValueError("Session is already cancelled.")

    session.status = Session.Status.CANCELLED
    session.save()
    return session


def end_session(session_id, report_summary: str) -> Session:
    session = Session.objects.get(id=session_id)

    if session.status in [Session.Status.COMPLETED, Session.Status.CANCELLED]:
        raise ValueError("This session cannot be ended (already completed or cancelled).")

    session.status = Session.Status.COMPLETED
    session.end_time = timezone.now()
    session.report_summary = report_summary.strip()
    session.save()
    return session


def update_session_report(session_id, report_summary: str) -> Session:
    if not report_summary or not report_summary.strip():
        raise ValueError("Report summary cannot be empty.")

    session = Session.objects.get(id=session_id)
    session.report_summary = report_summary.strip()
    session.save()
    return session


def search_sessions(queryset, search_query: str):
    from django.db.models import Q

    if not search_query:
        return queryset

    parts = search_query.strip().split()
    if len(parts) >= 2:
        first, last = parts[0], " ".join(parts[1:])
        return queryset.filter(
            Q(patient__user__first_name__icontains=first, patient__user__last_name__icontains=last)
            | Q(doctor__employee__user__first_name__icontains=first, doctor__employee__user__last_name__icontains=last)
        )

    return queryset.filter(
        Q(patient__user__first_name__icontains=search_query)
        | Q(patient__user__last_name__icontains=search_query)
        | Q(doctor__employee__user__first_name__icontains=search_query)
        | Q(doctor__employee__user__last_name__icontains=search_query)
    )


def get_session_stats() -> dict:
    today = date.today()
    return {
        "total_today": Session.objects.filter(start_time__date=today).count(),
        "waiting":     Session.objects.filter(status=Session.Status.SCHEDULED).count(),
        "in_progress": Session.objects.filter(status=Session.Status.IN_PROGRESS).count(),
        "completed":   Session.objects.filter(status=Session.Status.COMPLETED).count(),
    }
