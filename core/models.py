from django.db import models
from django.contrib.auth.models import AbstractUser
from pgvector.django import VectorField
import uuid


class User(AbstractUser):

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        DOCTOR = "doctor", "Doctor"
        RECEPTIONIST = "receptionist", "Receptionist"
    
        #اضافة حقول جديدة  fields

    email = models.EmailField(unique=True)      
    date_of_birth = models.DateField(null=True, blank=True) #اختياري
    phone = models.CharField(max_length=20, null=True, blank=True)

    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email



class Employee(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    employee_number = models.CharField(max_length=50, unique=True)
    department_name = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.employee_number:
            self.employee_number = f"EMP-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)


class Doctor(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    specialization = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Patient(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    gender = models.CharField(max_length=10, null=True, blank=True)
    doctor = models.ForeignKey(Doctor, null=True, blank=True, on_delete=models.SET_NULL)
    face_embedding = VectorField(dimensions=512)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Camera(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        MAINTENANCE = "maintenance", "Maintenance"

    location_name = models.CharField(max_length=255)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ONLINE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Session(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED
    )

    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    report_summary = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class EmotionResult(models.Model):
    class EmotionType(models.TextChoices):
        NEUTRAL = "neutral", "Neutral"
        HAPPY = "happy", "Happy"
        SAD = "sad", "Sad"
        ANGRY = "angry", "Angry"
        SURPRISED = "surprised", "Surprised"
        SCARED = "scared", "Scared"
        DISGUSTED = "disgusted", "Disgusted"
        DISTRESSED = "distressed", "Distressed"

    session = models.ForeignKey(Session, on_delete=models.CASCADE)
    camera = models.ForeignKey(Camera, null=True, blank=True, on_delete=models.SET_NULL)

    emotion = models.CharField(
        max_length=20,
        choices=EmotionType.choices,
        default=EmotionType.NEUTRAL
    )

    percentage = models.DecimalField(max_digits=5, decimal_places=2)

    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)



class Alert(models.Model):
    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        TRIGGERED = "triggered", "Triggered"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="alerts", null=True)
    message = models.TextField(default="")
    timestamp = models.DateTimeField(null=True, blank=True)

    severity = models.CharField(
        max_length=20,
        choices=Severity.choices,
        default=Severity.MEDIUM
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIGGERED
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Alert {self.id} - {self.session} - {self.severity}"



