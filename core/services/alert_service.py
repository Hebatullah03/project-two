from django.core.exceptions import PermissionDenied
from django.db.models import Case, IntegerField, When
from core.models import Alert, Doctor, User


def get_alerts_for_doctor(user):
    
    try:
        doctor = Doctor.objects.get(employee__user=user)
    except Doctor.DoesNotExist:
        raise PermissionDenied("You do not have permission to perform this action.")

    return (
        Alert.objects
        .filter(session__patient__doctor=doctor)
        .select_related("session__patient__user")
        .annotate(**_ordering_annotations())
        .order_by("status_order", "severity_order", "-created_at")
    )


def get_all_alerts():
    return (
        Alert.objects
        .all()
        .select_related("session__patient__user", "session__patient__doctor__employee__user")
        .annotate(**_ordering_annotations())
        .order_by("status_order", "severity_order", "-created_at")
    )


def get_alert_counts(alerts) -> dict:
    return {
        "high_count": alerts.filter(
            severity__in=[Alert.Severity.HIGH, Alert.Severity.CRITICAL],
            status=Alert.Status.TRIGGERED,
        ).count(),
        "medium_count": alerts.filter(
            severity=Alert.Severity.MEDIUM,
            status=Alert.Status.TRIGGERED,
        ).count(),
        "low_count": alerts.filter(
            severity=Alert.Severity.LOW,
            status=Alert.Status.TRIGGERED,
        ).count(),
    }


def acknowledge_alert(alert_id, user: User) -> Alert:
    _require_role(user, [User.Role.DOCTOR, User.Role.RECEPTIONIST])

    alert = Alert.objects.get(id=alert_id)

    if alert.status != Alert.Status.TRIGGERED:
        raise ValueError(f"Alert cannot be acknowledged from status '{alert.status}'.")

    alert.status = Alert.Status.ACKNOWLEDGED
    alert.save()
    return alert


def resolve_alert(alert_id, user: User) -> Alert:
    _require_role(user, [User.Role.DOCTOR])

    alert = Alert.objects.get(id=alert_id)

    if alert.status == Alert.Status.RESOLVED:
        raise ValueError("Alert is already resolved.")

    alert.status = Alert.Status.RESOLVED
    alert.save()
    return alert


def update_alert_status(alert_id, new_status: str, user: User) -> Alert:
    if new_status == Alert.Status.ACKNOWLEDGED:
        return acknowledge_alert(alert_id, user)
    if new_status == Alert.Status.RESOLVED:
        return resolve_alert(alert_id, user)
    raise ValueError(f"Unknown alert status: '{new_status}'.")


def _require_role(user: User, roles: list[str]) -> None:
    """Raise PermissionDenied if user has none of the required roles."""
    if not user.groups.filter(name__in=roles).exists():
        raise PermissionDenied("You do not have permission to perform this action.")


def _ordering_annotations() -> dict:
    """ORM annotations for deterministic alert ordering."""
    return {
        "status_order": Case(
            When(status=Alert.Status.TRIGGERED,    then=1),
            When(status=Alert.Status.ACKNOWLEDGED, then=2),
            When(status=Alert.Status.RESOLVED,     then=3),
            default=4,
            output_field=IntegerField(),
        ),
        "severity_order": Case(
            When(severity=Alert.Severity.CRITICAL, then=1),
            When(severity=Alert.Severity.HIGH,     then=2),
            When(severity=Alert.Severity.MEDIUM,   then=3),
            When(severity=Alert.Severity.LOW,      then=4),
            default=5,
            output_field=IntegerField(),
        ),
    }
