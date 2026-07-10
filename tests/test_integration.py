import pytest
from unittest.mock import MagicMock, patch
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.utils import timezone
from core.services import auth_service, patient_service, session_service, alert_service
from core.models import Alert, Doctor, Employee, Patient, Session, User


@pytest.fixture
def doctor_group(db):
    return Group.objects.get_or_create(name=User.Role.DOCTOR)[0]

@pytest.fixture
def receptionist_group(db):
    return Group.objects.get_or_create(name=User.Role.RECEPTIONIST)[0]

@pytest.fixture
def doctor_user(db, doctor_group):
    u = User.objects.create_user(username="doc@i.com", email="doc@i.com",
                                  password="pass123", first_name="Ahmed", last_name="Khalil")
    u.groups.add(doctor_group)
    return u

@pytest.fixture
def receptionist_user(db, receptionist_group):
    u = User.objects.create_user(username="rec@i.com", email="rec@i.com",
                                  password="pass123", first_name="Sara", last_name="Ali")
    u.groups.add(receptionist_group)
    return u

@pytest.fixture
def plain_user(db):
    return User.objects.create_user(username="plain@i.com", email="plain@i.com", password="x")

@pytest.fixture
def employee(db, doctor_user):
    return Employee.objects.create(user=doctor_user)

@pytest.fixture
def doctor(db, employee):
    return Doctor.objects.create(employee=employee)

@pytest.fixture
def patient(db, doctor):
    u = User.objects.create_user(username="pat@i.com", email="pat@i.com",
                                  password="x", first_name="Rania", last_name="Nasser")
    return Patient.objects.create(user=u, gender="F", doctor=doctor, face_embedding=[0.1]*128)

@pytest.fixture
def session(db, patient, doctor):
    return Session.objects.create(
        patient=patient, doctor=doctor,
        start_time=timezone.now(), status=Session.Status.SCHEDULED
    )

@pytest.fixture
def triggered_alert(db, session):
    return Alert.objects.create(
        session=session, severity=Alert.Severity.HIGH,
        status=Alert.Status.TRIGGERED, message="High distress"
    )



@pytest.mark.django_db
class TestAuthIntegration:

    def test_get_user_role_returns_doctor(self, doctor_user):
        assert auth_service.get_user_role(doctor_user) == User.Role.DOCTOR

    def test_get_user_role_returns_receptionist(self, receptionist_user):
        assert auth_service.get_user_role(receptionist_user) == User.Role.RECEPTIONIST

    def test_get_user_role_returns_none_for_plain_user(self, plain_user):
        assert auth_service.get_user_role(plain_user) is None

    def test_update_profile_persists(self, doctor_user):
        auth_service.update_profile(doctor_user, "Waleed", "Saleh", "0791112233")
        doctor_user.refresh_from_db()
        assert doctor_user.first_name == "Waleed"
        assert doctor_user.phone      == "0791112233"

    def test_update_profile_empty_phone_is_none(self, doctor_user):
        auth_service.update_profile(doctor_user, "Waleed", "Saleh", "")
        doctor_user.refresh_from_db()
        assert doctor_user.phone is None

    def test_change_password_actually_changes(self, plain_user):
        request = MagicMock()
        request.user = plain_user
        auth_service.change_password(request, "x", "newpass123", "newpass123")
        plain_user.refresh_from_db()
        assert plain_user.check_password("newpass123")

    def test_change_password_wrong_current_does_not_save(self, plain_user):
        request = MagicMock()
        request.user = plain_user
        with pytest.raises(ValueError):
            auth_service.change_password(request, "WRONG", "new", "new")
        plain_user.refresh_from_db()
        assert plain_user.check_password("x")



@pytest.mark.django_db
class TestPatientIntegration:

    @patch("core.services.patient_service.get_face_embedding", return_value=[0.1]*128)
    def test_create_persists_user_and_patient(self, _):
        p = patient_service.create_patient("Omar", "Farouk", "omar@t.com", "079", "M", "1988-03-15", None, MagicMock())
        assert p.pk is not None
        assert Patient.objects.filter(pk=p.pk).exists()
        assert p.user.email == "omar@t.com"

    @patch("core.services.patient_service.get_face_embedding", return_value=[0.1]*128)
    def test_create_duplicate_email_raises_integrity_error(self, _):
        patient_service.create_patient("A", "B", "dup@t.com", "1", "M", "1990-01-01", None, MagicMock())
        with pytest.raises(IntegrityError):
            patient_service.create_patient("C", "D", "dup@t.com", "2", "F", "1991-01-01", None, MagicMock())

    @patch("core.services.patient_service.get_face_embedding", return_value=[0.2]*128)
    def test_update_persists_name_change(self, _, patient):
        patient_service.update_patient(patient.pk, "Rania", "Updated", patient.user.email,
                                       "079", "F", "1995-06-15", None)
        patient.user.refresh_from_db()
        assert patient.user.last_name == "Updated"

    @patch("core.services.patient_service.get_face_embedding", return_value=[0.9]*128)
    def test_update_with_new_image_replaces_embedding(self, _, patient):
        old = list(patient.face_embedding)
        patient_service.update_patient(patient.pk, "Rania", "Nasser", patient.user.email,
                                       "079", "F", "1995-01-01", None, MagicMock())
        patient.refresh_from_db()
        assert list(patient.face_embedding) != old

    def test_search_by_last_name(self, patient):
        qs = Patient.objects.select_related("user").all()
        assert patient_service.search_patients(qs, "Nasser").filter(pk=patient.pk).exists()

    def test_search_two_part_name(self, patient):
        qs = Patient.objects.select_related("user").all()
        assert patient_service.search_patients(qs, "Rania Nasser").filter(pk=patient.pk).exists()

    def test_search_no_match(self, patient):
        qs = Patient.objects.select_related("user").all()
        assert not patient_service.search_patients(qs, "ZZZNoMatch").exists()

    def test_get_patients_for_doctor_includes_assigned(self, doctor, patient):
        ids = [p.pk for p in patient_service.get_patients_for_doctor(doctor)]
        assert patient.pk in ids



@pytest.mark.django_db
class TestSessionIntegration:

    def test_create_persists_with_scheduled_status(self, patient, doctor):
        s = session_service.create_session(patient.pk, doctor.pk, "2025-08-01", "10:00")
        assert s.pk is not None
        assert s.status == Session.Status.SCHEDULED

    def test_update_changes_start_time(self, session, patient, doctor):
        session_service.update_session(session.pk, patient.pk, doctor.pk, "2025-09-10", "14:30")
        session.refresh_from_db()
        assert session.start_time.hour == 14

    def test_cancel_sets_cancelled(self, session):
        session_service.cancel_session(session.pk)
        session.refresh_from_db()
        assert session.status == Session.Status.CANCELLED

    def test_cancel_already_cancelled_raises_value_error(self, session):
        session.status = Session.Status.CANCELLED
        session.save()
        with pytest.raises(ValueError, match="already cancelled"):
            session_service.cancel_session(session.pk)

    def test_end_session_marks_completed(self, session):
        session.status = Session.Status.IN_PROGRESS
        session.save()
        ended = session_service.end_session(session.pk, "Patient improving.")
        ended.refresh_from_db()
        assert ended.status == Session.Status.COMPLETED
        assert ended.report_summary == "Patient improving."
        assert ended.end_time is not None

    def test_end_session_empty_report_raises_value_error(self, session):
        with pytest.raises(ValueError, match="required"):
            session_service.end_session(session.pk, "  ")

    def test_update_report_persists(self, session):
        session_service.update_session_report(session.pk, "Updated notes")
        session.refresh_from_db()
        assert session.report_summary == "Updated notes"

    def test_get_session_stats_includes_scheduled(self, session):
        stats = session_service.get_session_stats()
        assert stats["waiting"] >= 1



@pytest.mark.django_db
class TestAlertIntegration:

    def test_get_alerts_for_doctor_includes_triggered(self, doctor, triggered_alert):
        assert alert_service.get_alerts_for_doctor(doctor.employee.user).filter(pk=triggered_alert.pk).exists()

    def test_get_all_alerts_includes_triggered(self, triggered_alert):
        assert alert_service.get_all_alerts().filter(pk=triggered_alert.pk).exists()

    def test_get_alert_counts_high_count(self, triggered_alert):
        counts = alert_service.get_alert_counts(alert_service.get_all_alerts())
        assert counts["high_count"] >= 1

    def test_acknowledge_by_receptionist_sets_acknowledged(self, triggered_alert, receptionist_user):
        alert_service.acknowledge_alert(triggered_alert.pk, receptionist_user)
        triggered_alert.refresh_from_db()
        assert triggered_alert.status == Alert.Status.ACKNOWLEDGED

    def test_acknowledge_by_plain_user_raises_permission_denied(self, triggered_alert, plain_user):
        with pytest.raises(PermissionDenied):
            alert_service.acknowledge_alert(triggered_alert.pk, plain_user)

    def test_acknowledge_already_acknowledged_raises_value_error(self, triggered_alert, receptionist_user):
        triggered_alert.status = Alert.Status.ACKNOWLEDGED
        triggered_alert.save()
        with pytest.raises(ValueError, match="cannot be acknowledged"):
            alert_service.acknowledge_alert(triggered_alert.pk, receptionist_user)

    def test_resolve_by_doctor_sets_resolved(self, triggered_alert, doctor_user):
        triggered_alert.status = Alert.Status.ACKNOWLEDGED
        triggered_alert.save()
        alert_service.resolve_alert(triggered_alert.pk, doctor_user)
        triggered_alert.refresh_from_db()
        assert triggered_alert.status == Alert.Status.RESOLVED

    def test_resolve_by_receptionist_raises_permission_denied(self, triggered_alert, receptionist_user):
        with pytest.raises(PermissionDenied, match="You do not have permission to perform this action."):
            alert_service.resolve_alert(triggered_alert.pk, receptionist_user)

    def test_resolve_already_resolved_raises_value_error(self, triggered_alert, doctor_user):
        triggered_alert.status = Alert.Status.RESOLVED
        triggered_alert.save()
        with pytest.raises(ValueError, match="already resolved"):
            alert_service.resolve_alert(triggered_alert.pk, doctor_user)

    def test_update_alert_status_unknown_raises_value_error(self, triggered_alert, doctor_user):
        with pytest.raises(ValueError, match="Unknown alert status"):
            alert_service.update_alert_status(triggered_alert.pk, "vaporize", doctor_user)
