import pytest
from unittest.mock import MagicMock, patch
from django.core.exceptions import PermissionDenied
from core.services import auth_service, patient_service, session_service, alert_service
from core.models import User, Session, Alert, Doctor, Patient
from django.db import IntegrityError



class TestAuthService:

    @patch("core.services.auth_service.django_authenticate", return_value=None)
    def test_login_raises_value_error_on_bad_credentials(self, _):
        with pytest.raises(ValueError, match="Invalid email or password"):
            auth_service.login_user(MagicMock(), "x@x.com", "wrong")

    @patch("core.services.auth_service.django_login")
    @patch("core.services.auth_service.django_authenticate")
    def test_login_returns_user_and_calls_login(self, mock_auth, mock_login):
        fake_user = MagicMock()
        mock_auth.return_value = fake_user
        request = MagicMock()
        result = auth_service.login_user(request, "doc@x.com", "pass")
        assert result is fake_user
        mock_login.assert_called_once_with(request, fake_user)

    @patch("core.services.auth_service.django_logout")
    def test_logout_delegates_to_django(self, mock_logout):
        request = MagicMock()
        auth_service.logout_user(request)
        mock_logout.assert_called_once_with(request)

    def test_get_user_role_doctor(self):
        user = MagicMock()
        user.groups.filter.return_value.exists.side_effect = [True, False]
        assert auth_service.get_user_role(user) == User.Role.DOCTOR

    def test_get_user_role_receptionist(self):
        user = MagicMock()
        user.groups.filter.return_value.exists.side_effect = [False, True]
        assert auth_service.get_user_role(user) == User.Role.RECEPTIONIST

    def test_get_user_role_none_when_no_group(self):
        user = MagicMock()
        user.groups.filter.return_value.exists.return_value = False
        assert auth_service.get_user_role(user) is None

    def test_redirect_url_for_doctor(self):
        assert auth_service.get_redirect_url_for_role(User.Role.DOCTOR) == "/doctor/patients/"

    def test_redirect_url_for_receptionist(self):
        from core.models import User
        assert auth_service.get_redirect_url_for_role(User.Role.RECEPTIONIST) == "/receptionist/dashboard/"

    def test_redirect_url_defaults_to_slash(self):
        assert auth_service.get_redirect_url_for_role(None) == "/"
    def test_change_password_raises_when_any_field_empty(self):
        with pytest.raises(ValueError, match="required"):
            auth_service.change_password(MagicMock(), "", "new", "new")

    def test_change_password_raises_on_wrong_current(self):
        request = MagicMock()
        request.user.check_password.return_value = False
        with pytest.raises(ValueError, match="incorrect"):
            auth_service.change_password(request, "bad", "new", "new")

    def test_change_password_raises_when_new_passwords_mismatch(self):
        request = MagicMock()
        request.user.check_password.return_value = True
        with pytest.raises(ValueError, match="do not match"):
            auth_service.change_password(request, "cur", "a", "b")

    @patch("core.services.auth_service.update_session_auth_hash")
    def test_change_password_saves_and_keeps_session(self, mock_hash):
        request = MagicMock()
        request.user.check_password.return_value = True
        auth_service.change_password(request, "cur", "new", "new")
        request.user.set_password.assert_called_once_with("new")
        request.user.save.assert_called_once()
        mock_hash.assert_called_once_with(request, request.user)

    def test_update_profile_strips_whitespace(self):
        user = MagicMock()
        auth_service.update_profile(user, "  Ali  ", "  Hasan  ", "  079  ")
        assert user.first_name == "Ali"
        assert user.last_name  == "Hasan"
        assert user.phone      == "079"

    def test_update_profile_empty_phone_becomes_none(self):
        user = MagicMock()
        auth_service.update_profile(user, "Ali", "Hasan", "")
        assert user.phone is None


class TestPatientService:

    @patch("core.services.patient_service.User.objects")
    @patch("core.services.patient_service.Patient.objects")
    def test_create_raises_when_face_image_missing(self, mock_patient, mock_user):
        with pytest.raises(ValueError, match="Face image is required."):
            patient_service.create_patient(
                first_name="A", 
                last_name="B", 
                email="a@b.com",
                phone="1", 
                gender="M", 
                date_of_birth="1990-01-01",
                doctor_id=None,
                face_image=None 
            )

    @patch("core.services.patient_service.User.objects")
    @patch("core.services.patient_service.Patient.objects")
    @patch("core.services.patient_service.get_face_embedding", return_value=None)
    def test_create_raises_when_no_face_detected(self, _, mock_patient, mock_user):
        with pytest.raises(ValueError, match="No face detected"):
            patient_service.create_patient("A", "B", "a@b.com", "1", "M", "1990-01-01", None, MagicMock())


    @patch("core.services.patient_service.transaction.atomic")
    @patch("core.services.patient_service.Patient.objects")
    @patch("core.services.patient_service.User.objects")
    @patch("core.services.patient_service.get_face_embedding", return_value=[0.1] * 128)
    def test_create_returns_patient_on_success(
        self,
        mock_embedding,
        mock_user_objects,
        mock_patient_objects,
        mock_atomic,
    ):
        fake_patient = MagicMock()

        mock_user_objects.create.return_value = MagicMock()
        mock_patient_objects.create.return_value = fake_patient

        result = patient_service.create_patient(
            "A", "B", "a@b.com", "1", "M", "1990-01-01", None, MagicMock()
        )

        assert result is fake_patient


    @patch("core.services.patient_service.transaction.atomic")
    @patch("core.services.patient_service.Patient.objects")
    @patch("core.services.patient_service.User.objects")
    @patch("core.services.patient_service.get_face_embedding", return_value=[0.1] * 128)
    def test_create_lets_integrity_error_bubble(self, _, mock_user_qs, mock_patient_qs, mock_atomic):
        mock_user_qs.create.side_effect = IntegrityError("duplicate")
        with pytest.raises(IntegrityError):
            patient_service.create_patient("A", "B", "dup@b.com", "1", "M", "1990-01-01", None, MagicMock())

    @patch("core.services.patient_service.transaction.atomic")
    @patch("core.services.patient_service.User.objects")
    @patch("core.services.patient_service.Patient.objects")
    @patch("core.services.patient_service.get_face_embedding", return_value=None)
    def test_update_raises_when_new_face_has_no_detection(self, _, mock_patient, mock_user, mock_atomic):
        fake = MagicMock()
        mock_patient.select_related.return_value.get.return_value = fake
        with pytest.raises(ValueError, match="No face detected"):
            patient_service.update_patient(1, "A", "B", "a@b.com", "1", "M", "1990-01-01", None, MagicMock())

    def test_search_empty_query_returns_queryset_unchanged(self):
        qs = MagicMock()
        result = patient_service.search_patients(qs, "")
        assert result is qs
        qs.filter.assert_not_called()

    def test_search_two_part_name_filters_first_and_last(self):
        qs = MagicMock()
        patient_service.search_patients(qs, "Rania Nasser")
        qs.filter.assert_called_once_with(
            user__first_name__icontains="Rania",
            user__last_name__icontains="Nasser",
        )

    def test_search_single_token_uses_q_filter(self):
        qs = MagicMock()
        patient_service.search_patients(qs, "rania")
        qs.filter.assert_called_once()   # Q(...) call, not kwargs


class TestSessionService:

    def test_create_raises_on_bad_date(self):
        with pytest.raises(ValueError, match="Invalid date or time"):
            session_service.create_session(1, 1, "not-a-date", "09:00")

    @patch("core.services.session_service.Session.objects")
    @patch("core.services.session_service.timezone.make_aware", return_value=MagicMock())
    def test_create_returns_session_on_success(self, _, mock_qs):
        fake = MagicMock()
        mock_qs.create.return_value = fake
        assert session_service.create_session(1, 2, "2025-06-01", "10:30") is fake

    @patch("core.services.session_service.Session.objects")
    def test_cancel_raises_if_already_cancelled(self, mock_qs):
        fake = MagicMock()
        fake.status = Session.Status.CANCELLED
        mock_qs.get.return_value = fake
        with pytest.raises(ValueError, match="already cancelled"):
            session_service.cancel_session(1)

    @patch("core.services.session_service.Session.objects")
    def test_cancel_sets_status_to_cancelled(self, mock_qs):
        fake = MagicMock()
        fake.status = Session.Status.SCHEDULED
        mock_qs.get.return_value = fake
        session_service.cancel_session(1)
        assert fake.status == Session.Status.CANCELLED
        fake.save.assert_called_once()

    def test_end_session_raises_without_report(self):
        with pytest.raises(ValueError, match="required"):
            session_service.end_session(1, "  ")

    @patch("core.services.session_service.Session.objects")
    def test_end_session_raises_if_already_completed(self, mock_qs):
        fake = MagicMock()
        fake.status = Session.Status.COMPLETED
        mock_qs.get.return_value = fake
        with pytest.raises(ValueError, match="cannot be ended"):
            session_service.end_session(1, "Some notes")

    @patch("core.services.session_service.timezone.now", return_value=MagicMock())
    @patch("core.services.session_service.Session.objects")
    def test_end_session_marks_completed_and_strips_report(self, mock_qs, _):
        fake = MagicMock()
        fake.status = Session.Status.IN_PROGRESS
        mock_qs.get.return_value = fake
        session_service.end_session(1, "  Notes  ")
        assert fake.status == Session.Status.COMPLETED
        assert fake.report_summary == "Notes"
        fake.save.assert_called_once()

    def test_update_report_raises_when_empty(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            session_service.update_session_report(1, "")

    @patch("core.services.session_service.Session.objects")
    def test_update_report_saves_stripped_text(self, mock_qs):
        fake = MagicMock()
        mock_qs.get.return_value = fake
        session_service.update_session_report(1, "  Updated  ")
        assert fake.report_summary == "Updated"
        fake.save.assert_called_once()

    def test_search_empty_query_passthrough(self):
        qs = MagicMock()
        assert session_service.search_sessions(qs, "") is qs

    def test_search_two_part_name_calls_filter(self):
        qs = MagicMock()
        session_service.search_sessions(qs, "Ali Hassan")
        qs.filter.assert_called_once()

    @patch("core.services.session_service.Session.objects")
    def test_get_session_stats_has_correct_keys(self, mock_qs):
        mock_qs.filter.return_value.count.return_value = 0
        stats = session_service.get_session_stats()
        assert set(stats) == {"total_today", "waiting", "in_progress", "completed"}



class TestAlertService:

    def test_acknowledge_raises_permission_denied_for_unknown_role(self):
        user = MagicMock()
        user.groups.filter.return_value.exists.return_value = False
        with pytest.raises(PermissionDenied):
            alert_service.acknowledge_alert(1, user)

    @patch("core.services.alert_service.Alert.objects")
    def test_acknowledge_raises_value_error_if_not_triggered(self, mock_qs):
        user = MagicMock()
        user.groups.filter.return_value.exists.return_value = True
        fake = MagicMock()
        fake.status = Alert.Status.ACKNOWLEDGED
        mock_qs.get.return_value = fake
        with pytest.raises(ValueError, match="cannot be acknowledged"):
            alert_service.acknowledge_alert(1, user)

    @patch("core.services.alert_service.Alert.objects")
    def test_acknowledge_sets_status(self, mock_qs):
        user = MagicMock()
        user.groups.filter.return_value.exists.return_value = True
        fake = MagicMock()
        fake.status = Alert.Status.TRIGGERED
        mock_qs.get.return_value = fake
        alert_service.acknowledge_alert(1, user)
        assert fake.status == Alert.Status.ACKNOWLEDGED
        fake.save.assert_called_once()

    def test_resolve_raises_permission_denied_for_non_doctor(self):
        user = MagicMock()
        user.groups.filter.return_value.exists.return_value = False
        with pytest.raises(PermissionDenied):
            alert_service.resolve_alert(1, user)

    @patch("core.services.alert_service.Alert.objects")
    def test_resolve_raises_value_error_if_already_resolved(self, mock_qs):
       
        user = MagicMock()
        user.groups.filter.return_value.exists.return_value = True
        fake = MagicMock()
        fake.status = Alert.Status.RESOLVED
        mock_qs.get.return_value = fake
        with pytest.raises(ValueError, match="already resolved"):
            alert_service.resolve_alert(1, user)

    @patch("core.services.alert_service.Alert.objects")
    def test_resolve_sets_status(self, mock_qs):
        user = MagicMock()
        user.groups.filter.return_value.exists.return_value = True
        fake = MagicMock()
        fake.status = Alert.Status.ACKNOWLEDGED
        mock_qs.get.return_value = fake
        alert_service.resolve_alert(1, user)
        assert fake.status == Alert.Status.RESOLVED
        fake.save.assert_called_once()

    def test_update_alert_status_raises_value_error_for_unknown_status(self):
        with pytest.raises(ValueError, match="Unknown alert status"):
            alert_service.update_alert_status(1, "banana", MagicMock())

    def test_get_alert_counts_returns_correct_keys(self):
        alerts = MagicMock()
        alerts.filter.return_value.count.return_value = 2
        counts = alert_service.get_alert_counts(alerts)
        assert set(counts) == {"high_count", "medium_count", "low_count"}
