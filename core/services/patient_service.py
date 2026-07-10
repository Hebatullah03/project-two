from django.db import IntegrityError, transaction
from django.db.models import Q, Value, CharField
from core.models import Doctor, Patient, User
from core.face_embedding import get_face_embedding


def create_patient(
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    gender: str,
    date_of_birth: str,
    doctor_id,
    face_image,
) -> Patient:
    if not face_image:
        raise ValueError("Face image is required.")

    embedding = get_face_embedding(face_image)
    if embedding is None:
        raise ValueError("No face detected in the provided image.")

    with transaction.atomic():
        user = User.objects.create(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            date_of_birth=date_of_birth,
        )

        return Patient.objects.create(
            user=user,
            gender=gender,
            doctor_id=doctor_id or None,
            face_embedding=embedding,
        )



def update_patient(
    patient_id: int,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    gender: str,
    date_of_birth: str,
    doctor_id,
    face_image=None,
) -> Patient:
    with transaction.atomic():
        patient = Patient.objects.select_related("user").get(id=patient_id)

        user = patient.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.phone = phone
        user.date_of_birth = date_of_birth
        user.save()

        patient.gender = gender
        patient.doctor_id = doctor_id or None

        if face_image:
            embedding = get_face_embedding(face_image)
            if not embedding:
                raise ValueError("No face detected in the provided image.")
            patient.face_embedding = embedding

        patient.save()
        return patient


def get_patients_for_doctor(doctor: Doctor):
    assigned = Patient.objects.select_related("user").filter(doctor=doctor).annotate(
        relation=Value("Assigned", output_field=CharField())
    )
    visited = (
        Patient.objects.select_related("user")
        .filter(session__doctor=doctor)
        .exclude(doctor=doctor)
        .distinct()
        .annotate(relation=Value("Visited", output_field=CharField()))
    )
    return assigned.union(visited)


def search_patients(queryset, search_query: str):
    if not search_query:
        return queryset

    parts = search_query.strip().split()
    if len(parts) >= 2:
        return queryset.filter(
            user__first_name__icontains=parts[0],
            user__last_name__icontains=" ".join(parts[1:]),
        )

    return queryset.filter(
        Q(user__first_name__icontains=search_query)
        | Q(user__last_name__icontains=search_query)
        | Q(user__email__icontains=search_query)
        | Q(user__phone__icontains=search_query)
    )
