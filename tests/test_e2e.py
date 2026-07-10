import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from unittest.mock import patch

from core.models import Alert, Doctor, Employee, Patient, Session, User


# ── fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def client():
    return Client()

@pytest.fixture
def doctor_group(db):
    return Group.objects.get_or_create(name=User.Role.DOCTOR)[0]

@pytest.fixture
def receptionist_group(db):
    return Group.objects.get_or_create(name=User.Role.RECEPTIONIST)[0]

@pytest.fixture
def doctor_user(db, doctor_group):
    u = User.objects.create_user(username="doc@e.com", email="doc@e.com",
                                  password="pass123", first_name="Dr", last_name="House")
    u.groups.add(doctor_group)
    return u

@pytest.fixture
def receptionist_user(db, receptionist_group):
    u = User.objects.create_user(username="rec@e.com", email="rec@e.com",
                                  password="pass123", first_name="Sara", last_name="Ali")
    u.groups.add(receptionist_group)
    return u

@pytest.fixture
def employee(db, doctor_user):
    return Employee.objects.create(user=doctor_user)

@pytest.fixture
def doctor(db, employee):
    return Doctor.objects.create(employee=employee)

@pytest.fixture
def patient(db, doctor):
    u = User.objects.create_user(username="pat@e.com", email="pat@e.com",
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
        status=Alert.Status.TRIGGERED, message="Test alert"
    )


# ════════════════════════════════════════════════════════════════
#  LOGIN / LOGOUT
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestLoginLogout:

    def test_get_renders_login_page(self, client):
        resp = client.get(reverse("core:login"))
        assert resp.status_code == 200

    def test_valid_doctor_redirects_to_doctor_dashboard(self, client, doctor_user):
        resp = client.post(reverse("core:login"), {"email": "doc@e.com", "password": "pass123"})
        assert resp.status_code == 302
        assert "/doctor/dashboard/" in resp["Location"]

    def test_valid_receptionist_redirects_to_receptionist_dashboard(self, client, receptionist_user):
        resp = client.post(reverse("core:login"), {"email": "rec@e.com", "password": "pass123"})
        assert resp.status_code == 302
        assert "/receptionist/dashboard/" in resp["Location"]

    def test_bad_credentials_re_renders_login(self, client, db):
        resp = client.post(reverse("core:login"), {"email": "x@x.com", "password": "wrong"})
        assert resp.status_code == 200      # re-render, not redirect

    def test_logout_redirects_to_login(self, client, doctor_user):
        client.force_login(doctor_user)
        resp = client.get(reverse("core:logout"))
        assert resp.status_code == 302
        assert "/auth/login/" in resp["Location"]


# ════════════════════════════════════════════════════════════════
#  PROFILE / PASSWORD
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestProfileAndPassword:

    def test_unauthenticated_profile_update_redirects(self, client):
        resp = client.post(reverse("core:update_profile"), {})
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_profile_update_persists(self, client, receptionist_user):
        client.force_login(receptionist_user)
        client.post(reverse("core:update_profile"),
                    {"first_name": "New", "last_name": "Name", "phone": ""})
        receptionist_user.refresh_from_db()
        assert receptionist_user.first_name == "New"

    def test_correct_password_change_works(self, client, receptionist_user):
        client.force_login(receptionist_user)
        client.post(reverse("core:change_password"), {
            "current_password": "pass123",
            "new_password":     "newSecure456",
            "confirm_password": "newSecure456",
        })
        receptionist_user.refresh_from_db()
        assert receptionist_user.check_password("newSecure456")

    def test_wrong_current_password_does_not_change(self, client, doctor_user):
        client.force_login(doctor_user)
        client.post(reverse("core:change_password"), {
            "current_password": "WRONG",
            "new_password":     "new123",
            "confirm_password": "new123",
        })
        doctor_user.refresh_from_db()
        assert doctor_user.check_password("pass123")

    def test_mismatched_new_passwords_does_not_change(self, client, doctor_user):
        client.force_login(doctor_user)
        client.post(reverse("core:change_password"), {
            "current_password": "pass123",
            "new_password":     "aaa",
            "confirm_password": "bbb",
        })
        doctor_user.refresh_from_db()
        assert doctor_user.check_password("pass123")


# ════════════════════════════════════════════════════════════════
#  DOCTOR SESSIONS
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDoctorSessions:

    def test_list_renders(self, client, doctor_user, doctor, session):
        client.force_login(doctor_user)
        assert client.get(reverse("core:doctor_sessions")).status_code == 200

    def test_search_by_name(self, client, doctor_user, doctor, session):
        client.force_login(doctor_user)
        assert client.get(reverse("core:doctor_sessions"), {"search": "Rania"}).status_code == 200

    def test_end_session_with_report_completes_it(self, client, doctor_user, doctor, session):
        session.status = Session.Status.IN_PROGRESS
        session.save()
        client.force_login(doctor_user)
        client.post(reverse("core:end_session", args=[session.pk]),
                    {"report_summary": "All good."})
        session.refresh_from_db()
        assert session.status == Session.Status.COMPLETED

    def test_end_session_without_report_does_not_complete(self, client, doctor_user, doctor, session):
        session.status = Session.Status.IN_PROGRESS
        session.save()
        client.force_login(doctor_user)
        client.post(reverse("core:end_session", args=[session.pk]),
                    {"report_summary": ""})
        session.refresh_from_db()
        assert session.status == Session.Status.IN_PROGRESS

    def test_end_already_completed_redirects_gracefully(self, client, doctor_user, doctor, session):
        session.status = Session.Status.COMPLETED
        session.save()
        client.force_login(doctor_user)
        resp = client.post(reverse("core:end_session", args=[session.pk]),
                           {"report_summary": "Again"})
        assert resp.status_code == 302

    def test_update_report_saves(self, client, doctor_user, doctor, session):
        client.force_login(doctor_user)
        client.post(reverse("core:update_session_report", args=[session.pk]),
                    {"report_summary": "Updated."})
        session.refresh_from_db()
        assert session.report_summary == "Updated."

    def test_update_report_empty_does_not_save(self, client, doctor_user, doctor, session):
        session.report_summary = "Original"
        session.save()
        client.force_login(doctor_user)
        client.post(reverse("core:update_session_report", args=[session.pk]),
                    {"report_summary": ""})
        session.refresh_from_db()
        assert session.report_summary == "Original"


# ════════════════════════════════════════════════════════════════
#  DOCTOR ALERTS
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDoctorAlerts:

    def test_list_renders(self, client, doctor_user, doctor, triggered_alert):
        client.force_login(doctor_user)
        assert client.get(reverse("core:doctor_alerts")).status_code == 200

    def test_doctor_can_resolve_acknowledged_alert(self, client, doctor_user, doctor, triggered_alert):
        triggered_alert.status = Alert.Status.ACKNOWLEDGED
        triggered_alert.save()
        client.force_login(doctor_user)
        client.post(
            reverse("core:update_alert_status", args=[triggered_alert.pk]),
            {"status": Alert.Status.RESOLVED},
            HTTP_REFERER=reverse("core:doctor_alerts"),
        )
        triggered_alert.refresh_from_db()
        assert triggered_alert.status == Alert.Status.RESOLVED


# ════════════════════════════════════════════════════════════════
#  RECEPTIONIST PATIENTS
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestReceptionistPatients:

    def test_list_renders(self, client, receptionist_user, patient):
        client.force_login(receptionist_user)
        assert client.get(reverse("core:receptionist_patients")).status_code == 200

    @patch("core.services.patient_service.get_face_embedding", return_value=[0.1]*128)
    def test_create_patient_persists(self, _, client, receptionist_user):
        client.force_login(receptionist_user)
        face = SimpleUploadedFile("f.jpg", b"bytes", content_type="image/jpeg")
        client.post(reverse("core:receptionist_patients"), {
            "first_name": "Lana", "last_name": "Rawi",
            "email": "lana@t.com", "phone": "079",
            "gender": "F", "date_of_birth": "2000-01-01",
            "face_image": face,
        })
        assert Patient.objects.filter(user__email="lana@t.com").exists()

    def test_create_without_face_does_not_persist(self, client, receptionist_user):
        client.force_login(receptionist_user)
        client.post(reverse("core:receptionist_patients"), {
            "first_name": "X", "last_name": "Y",
            "email": "xy@t.com", "phone": "0",
            "gender": "M", "date_of_birth": "1990-01-01",
        })
        assert not Patient.objects.filter(user__email="xy@t.com").exists()

    @patch("core.services.patient_service.get_face_embedding", return_value=None)
    def test_create_with_undetected_face_does_not_persist(self, _, client, receptionist_user):
        client.force_login(receptionist_user)
        face = SimpleUploadedFile("f.jpg", b"blank", content_type="image/jpeg")
        client.post(reverse("core:receptionist_patients"), {
            "first_name": "Z", "last_name": "W",
            "email": "zw@t.com", "phone": "0",
            "gender": "M", "date_of_birth": "1990-01-01",
            "face_image": face,
        })
        assert not Patient.objects.filter(user__email="zw@t.com").exists()

    @patch("core.services.patient_service.get_face_embedding", return_value=[0.1]*128)
    def test_duplicate_email_does_not_create_second_patient(self, _, client, receptionist_user, patient):
        client.force_login(receptionist_user)
        face = SimpleUploadedFile("f.jpg", b"x", content_type="image/jpeg")
        client.post(reverse("core:receptionist_patients"), {
            "first_name": "Copy", "last_name": "Cat",
            "email": patient.user.email,  # duplicate
            "phone": "0", "gender": "M", "date_of_birth": "1990-01-01",
            "face_image": face,
        })
        assert Patient.objects.filter(user__email=patient.user.email).count() == 1


# ════════════════════════════════════════════════════════════════
#  RECEPTIONIST SESSIONS
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestReceptionistSessions:

    def test_list_renders(self, client, receptionist_user, session):
        client.force_login(receptionist_user)
        assert client.get(reverse("core:receptionist_sessions")).status_code == 200

    def test_create_session_persists(self, client, receptionist_user, patient, doctor):
        client.force_login(receptionist_user)
        client.post(reverse("core:receptionist_sessions"), {
            "patient": patient.pk, "doctor": doctor.pk,
            "date": "2025-12-01", "time": "09:00",
        })
        assert Session.objects.filter(patient=patient, doctor=doctor).exists()

    def test_create_without_patient_does_not_persist(self, client, receptionist_user, doctor):
        before = Session.objects.count()
        client.force_login(receptionist_user)
        client.post(reverse("core:receptionist_sessions"), {
            "doctor": doctor.pk, "date": "2025-12-01", "time": "09:00",
        })
        assert Session.objects.count() == before

    def test_update_session_changes_time(self, client, receptionist_user, session, patient, doctor):
        client.force_login(receptionist_user)
        client.post(reverse("core:receptionist_sessions"), {
            "session_id": session.pk,
            "patient": patient.pk, "doctor": doctor.pk,
            "date": "2025-12-15", "time": "11:00",
        })
        session.refresh_from_db()
        assert session.start_time.hour == 11

    def test_cancel_session(self, client, receptionist_user, session):
        client.force_login(receptionist_user)
        client.post(reverse("core:cancel_session", args=[session.pk]))
        session.refresh_from_db()
        assert session.status == Session.Status.CANCELLED

    def test_cancel_already_cancelled_redirects_gracefully(self, client, receptionist_user, session):
        session.status = Session.Status.CANCELLED
        session.save()
        client.force_login(receptionist_user)
        resp = client.post(reverse("core:cancel_session", args=[session.pk]))
        assert resp.status_code == 302   # no crash


# ════════════════════════════════════════════════════════════════
#  RECEPTIONIST ALERTS
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestReceptionistAlerts:

    def test_list_renders(self, client, receptionist_user, triggered_alert):
        client.force_login(receptionist_user)
        assert client.get(reverse("core:receptionist_alerts")).status_code == 200

    def test_receptionist_can_acknowledge(self, client, receptionist_user, triggered_alert):
        client.force_login(receptionist_user)
        client.post(
            reverse("core:update_alert_status", args=[triggered_alert.pk]),
            {"status": Alert.Status.ACKNOWLEDGED},
            HTTP_REFERER=reverse("core:receptionist_alerts"),
        )
        triggered_alert.refresh_from_db()
        assert triggered_alert.status == Alert.Status.ACKNOWLEDGED

    def test_receptionist_cannot_resolve(self, client, receptionist_user, triggered_alert):
        client.force_login(receptionist_user)
        client.post(
            reverse("core:update_alert_status", args=[triggered_alert.pk]),
            {"status": Alert.Status.RESOLVED},
            HTTP_REFERER=reverse("core:receptionist_alerts"),
        )
        triggered_alert.refresh_from_db()
        assert triggered_alert.status == Alert.Status.TRIGGERED  # unchanged


# ════════════════════════════════════════════════════════════════
#  ACCESS CONTROL SWEEP
# ════════════════════════════════════════════════════════════════

@pytest.mark.django_db
@pytest.mark.parametrize("route_name", [
    "core:doctor_sessions",
    "core:doctor_alerts",
    "core:doctor_patients",
    "core:doctor_profile",
    "core:receptionist_patients",
    "core:receptionist_sessions",
    "core:receptionist_alerts",
    "core:receptionist_profile",
])
def test_unauthenticated_get_redirects_to_login(client, route_name):
    resp = client.get(reverse(route_name))
    assert resp.status_code == 302
    assert "login" in resp["Location"] or "/auth/" in resp["Location"]
