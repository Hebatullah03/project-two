from django.urls import path
from core.views import auth_view, doctor_view, receptionist_view
app_name = 'core'

urlpatterns = [
    path('', auth_view.home, name='home'),
    path('auth/login/', auth_view.login_view, name='login'),
    path('auth/logout/', auth_view.logout_view, name='logout'),
    path('receptionist/dashboard/', receptionist_view.receptionist_dashboard, name='receptionist_dashboard'),
    path('receptionist/patients/', receptionist_view.receptionist_patients, name='receptionist_patients'),
    path('receptionist/sessions/', receptionist_view.receptionist_sessions, name='receptionist_sessions'),
    path('receptionist/profile/', receptionist_view.receptionist_profile, name='receptionist_profile'),
    path('profile/update/', auth_view.update_profile, name='update_profile'),
    path('profile/change-password/', auth_view.change_password, name='change_password'),
    path('receptionist/alerts/', receptionist_view.receptionist_alerts, name='receptionist_alerts'),
    path("receptionist/sessions/<int:session_id>/cancel/", receptionist_view.cancel_session, name="cancel_session"),
    path('doctor/profile/', doctor_view.doctor_profile, name='doctor_profile'),
    path('doctor/profile/', doctor_view.doctor_profile, name='doctor_profile'),
    path('doctor/sessions/', doctor_view.doctor_sessions, name='doctor_sessions'),
    path('doctor/sessions/<int:session_id>/end/', doctor_view.end_session, name='doctor_end_session'),
    path('doctor/sessions/<int:session_id>/update-report/', doctor_view.update_session_report, name='update_session_report'),
    path('doctor/sessions/<int:session_id>/update-report/', doctor_view.update_session_report, name='doctor_update_session_report'),
    path('doctor/alerts/', doctor_view.doctor_alerts, name='doctor_alerts'),
    path('doctor/patients/', doctor_view.doctor_patients, name='doctor_patients'),
    path('doctor/analytics/', doctor_view.doctor_analytics, name='doctor_analytics'),
    path('alerts/<int:alert_id>/update-status/', receptionist_view.update_alert_status, name='update_alert_status'),
]
