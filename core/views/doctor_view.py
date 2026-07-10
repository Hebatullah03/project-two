import json
import logging
from collections import defaultdict
from datetime import date, timedelta
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Value, CharField
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from core.constant import WINDOW_DURATION_AFTER_MINS, WINDOW_DURATION_AFTER_MINS, WINDOW_DURATION_BEFORE_MINS
from core.services import patient_service, session_service, alert_service
from core.models import Alert, Doctor, EmotionResult, Patient, Session, User

logger = logging.getLogger(__name__)



def _require_auth(request):
    if not request.user.is_authenticated:
        return redirect("core:login")
    return None

def doctor_dashboard(request):
    guard = _require_auth(request)
    if guard:
        return guard
    return render(request, "doctor/patients.html")


def doctor_profile(request):
    guard = _require_auth(request)
    if guard:
        return guard
    return render(request, "doctor/profile.html", {"profile_user": request.user})


def doctor_sessions(request):
    guard = _require_auth(request)
    if guard:
        return guard

    doctor = get_object_or_404(Doctor, employee__user=request.user)
    sessions = Session.objects.select_related("patient__user").filter(doctor=doctor)

    search_query = request.GET.get("search", "")
    patient_id   = request.GET.get("patient_id", "")

    if patient_id:
        sessions = sessions.filter(patient__id=patient_id)
    elif search_query:
        sessions = session_service.search_sessions(sessions, search_query)

    sort_by  = request.GET.get("sort", "-start_time")
    sessions = sessions.order_by(sort_by)

    today = date.today()
    stats = {
        "total_today": sessions.filter(start_time__date=today).count(),
        "scheduled":   sessions.filter(status=Session.Status.SCHEDULED).count(),
        "in_progress": sessions.filter(status=Session.Status.IN_PROGRESS).count(),
        "completed":   sessions.filter(status=Session.Status.COMPLETED).count(),
    }

    paginator = Paginator(sessions, 10)
    page_obj  = paginator.get_page(request.GET.get("page"))

    return render(request, "doctor/sessions.html", {
        "sessions":     page_obj,
        "search_query": search_query,
        "sort_by":      sort_by,
        "stats":        stats,
    })


@require_POST
def end_session(request, session_id):
    guard = _require_auth(request)
    if guard:
        return guard

    try:
        session_service.end_session(
            session_id=session_id,
            report_summary=request.POST.get("report_summary", ""),
        )
        messages.success(request, "Session ended successfully.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("core:doctor_sessions")


@require_POST
def update_session_report(request, session_id):
    guard = _require_auth(request)
    if guard:
        return guard

    try:
        session_service.update_session_report(
            session_id=session_id,
            report_summary=request.POST.get("report_summary", ""),
        )
        messages.success(request, "Report summary updated successfully.")
    except ValueError as exc:
        messages.error(request, str(exc))

    return redirect("core:doctor_sessions")


def doctor_alerts(request):
    guard = _require_auth(request)
    if guard:
        return guard
    try:
        alerts = alert_service.get_alerts_for_doctor(request.user)
    except PermissionError as exc:
        logger.error("Error getting alerts for doctor: %s", exc)
        return redirect("core:login")

    counts = alert_service.get_alert_counts(alerts) 

    return render(request, "doctor/alerts.html", {"alerts": alerts, **counts, "Alert": Alert})


def doctor_patients(request):
    guard = _require_auth(request)
    if guard:
        return guard

    doctor       = get_object_or_404(Doctor, employee__user=request.user)
    search_query = request.GET.get("search", "")
    sort_by      = request.GET.get("sort", "name_asc")

    if search_query:
        assigned = patient_service.search_patients(
            Patient.objects.select_related("user").filter(doctor=doctor), search_query
        ).annotate(relation=Value("Assigned", output_field=CharField()))


        visited = patient_service.search_patients(
            Patient.objects.select_related("user")
            .filter(session__doctor=doctor).exclude(doctor=doctor).distinct(),
            search_query,
        ).annotate(relation=Value("Visited", output_field=CharField()))

        
        patients = assigned.union(visited)
    else:
        patients = patient_service.get_patients_for_doctor(doctor)

    sort_map = {
        "name_asc":  ("user__first_name", "user__last_name"),
        "name_desc": ("-user__first_name", "-user__last_name"),
        "dob":       ("user__date_of_birth",),
    }
    patients = patients.order_by(*sort_map.get(sort_by, ("-id",)))

    paginator = Paginator(patients, 10)
    page_obj  = paginator.get_page(request.GET.get("page"))

    return render(request, "doctor/patients.html", {
        "patients":     page_obj,
        "search_query": search_query,
        "sort_by":      sort_by,
    })


def doctor_analytics(request):
    guard = _require_auth(request)
    if guard:
        return guard

    doctor        = get_object_or_404(Doctor, employee__user=request.user)
    WINDOW_SIZE   = int(request.GET.get("window",   30))
    EMOTIONS      = ["neutral", "happy", "sad", "angry", "surprised", "scared", "disgusted", "distressed"]

    all_patients = (
        Patient.objects.select_related("user")
        .filter(Q(doctor=doctor) | Q(session__doctor=doctor))
        .distinct()
        .order_by("user__first_name", "user__last_name")
    )

    selected_patient_id  = request.GET.get("patient", "")
    selected_session_id  = request.GET.get("session", "")
    sessions             = []
    chart_labels         = []
    datasets             = {e: [] for e in EMOTIONS}
    summary              = {}
    session_overview     = None

    if selected_patient_id:
        sessions = list(
            Session.objects
            .filter(patient_id=selected_patient_id, doctor=doctor)
            .order_by("start_time")
        )

    if selected_patient_id and not selected_session_id and sessions:
        session_ids = [s.id for s in sessions]
        all_results = EmotionResult.objects.filter(session_id__in=session_ids).values("session_id", "emotion")

        counts = defaultdict(lambda: {e: 0 for e in EMOTIONS})
        for r in all_results:
            emo = r["emotion"].lower()
            if emo in counts[r["session_id"]]:
                counts[r["session_id"]][emo] += 1

        session_overview = []
        for s in sessions:
            emo_counts = counts[s.id]
            total      = sum(emo_counts.values())
            pct        = {e: round(emo_counts[e] / total * 100, 1) if total else 0 for e in EMOTIONS}
            dominant   = max(emo_counts, key=emo_counts.get) if total else "N/A"
            label      = f"Session #{s.id}"
            if s.start_time:
                label += f" ({s.start_time.strftime('%b %d')})"
            session_overview.append({
                "id": s.id, "label": label,
                "status": s.get_status_display(),
                "total": total, "pct": pct,
                "dominant": dominant.capitalize(),
            })

    if selected_session_id and selected_patient_id:
        session_obj = get_object_or_404(Session, id=selected_session_id, doctor=doctor)
        results     = list(
            EmotionResult.objects
            .filter(session_id=selected_session_id)
            .order_by("start_time")
            .values("emotion", "start_time")
        )

        anchor  = session_obj.start_time - timedelta(minutes=WINDOW_DURATION_BEFORE_MINS)
        if anchor is not None:
            horizon = session_obj.start_time + timedelta(minutes=WINDOW_DURATION_AFTER_MINS)
            num_buckets = ((WINDOW_DURATION_BEFORE_MINS + WINDOW_DURATION_AFTER_MINS) * 60) // WINDOW_SIZE + 1
            buckets     = {i: {e: 0 for e in EMOTIONS} for i in range(num_buckets)}

            for r in results:
                t = r["start_time"]
                if t < anchor or t >= horizon:
                    continue
                idx = int((t - anchor).total_seconds() // WINDOW_SIZE)
                if idx < num_buckets and r["emotion"].lower() in buckets[idx]:
                    buckets[idx][r["emotion"].lower()] += 1

            offset_seconds = WINDOW_DURATION_BEFORE_MINS * 60

            for i in range(num_buckets):
                elapsed_seconds = (i * WINDOW_SIZE) - offset_seconds

          
                total_abs = abs(elapsed_seconds)
                mins, secs = divmod(total_abs, 60)

                if elapsed_seconds < 0:
                    label = f"-{mins:02d}:{secs:02d}"
                elif elapsed_seconds == 0:
                    label = "00:00"
                else:
                    label = f"+{mins:02d}:{secs:02d}"

                chart_labels.append(label)

                bucket_total = sum(buckets[i].values())

                for emo in EMOTIONS:
                    datasets[emo].append(
                        round(buckets[i][emo] / bucket_total * 100, 1) if bucket_total else 0
                    )

            total_readings = len(results)
            emo_counts     = {e: 0 for e in EMOTIONS}
            for r in results:
                emo = r["emotion"].lower()
                if emo in emo_counts:
                    emo_counts[emo] += 1

            dominant_emotion = max(emo_counts, key=emo_counts.get) if total_readings else "N/A"
            dominant_pct     = round(emo_counts.get(dominant_emotion, 0) / total_readings * 100, 1) if total_readings else 0

            distress_emotions              = ["sad", "angry", "scared", "distressed"]
            worst_bucket_idx, worst_score  = 0, -1
            for i in range(num_buckets):
                score = sum(datasets[e][i] for e in distress_emotions)
                if score > worst_score:
                    worst_score, worst_bucket_idx = score, i

            summary = {
                "total_readings":  total_readings,
                "dominant_emotion": dominant_emotion.capitalize(),
                "dominant_pct":     dominant_pct,
                "worst_window":     chart_labels[worst_bucket_idx] if chart_labels else "N/A",
                "worst_score":      round(worst_score, 1),
                "window_size":      WINDOW_SIZE,
                "duration_mins":    WINDOW_DURATION_AFTER_MINS,
                "overall": {e: round(emo_counts[e] / total_readings * 100, 1) if total_readings else 0 for e in EMOTIONS},
            }

    print("chart_labels:", chart_labels)
    print("datasets:", datasets)
    return render(request, "doctor/analytics.html", {
        "patients":              all_patients,
        "sessions":              sessions,
        "selected_patient_id":   selected_patient_id,
        "selected_session_id":   selected_session_id,
        "window_size":           WINDOW_SIZE,
        "duration_mins":         WINDOW_DURATION_AFTER_MINS,
        "chart_labels":          json.dumps(chart_labels),
        "datasets":              json.dumps(datasets),
        "summary":               summary,
        "summary_overall_json":  json.dumps(summary.get("overall", {})),
        "emotions":              EMOTIONS,
        "session_overview":      json.dumps(session_overview) if session_overview is not None else "null",
        "session_overview_list": session_overview,
    })

