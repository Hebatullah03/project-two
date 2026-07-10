from django.contrib import admin

from django.contrib.auth.models import Group
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from .models import (
    User,
    Employee,
    Doctor,
    Patient,
    Camera,
    Session,
    EmotionResult,
    Alert,
)

User = get_user_model()



class EmployeeAdminForm(forms.ModelForm):
    email = forms.EmailField()
    username = forms.CharField(required=False)
    password = forms.CharField(widget=forms.PasswordInput) #بتغطي كلة السر **** 
    phone = forms.CharField(required=False)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    ROLE_CHOICES = (
        ("receptionist", "Receptionist"),
        ("doctor", "Doctor"),
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    is_active = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = Employee
        fields = ("email", "username", "password", "phone", "role")


class DoctorAdminForm(forms.ModelForm):
    email = forms.EmailField()
    username = forms.CharField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    phone = forms.CharField(required=False)
    specialization = forms.CharField(required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)

    class Meta:
        model = Doctor
        fields = (
            "email",
            "username",
            "password",
            "phone",
            "specialization",
            "is_active",
        )


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "is_staff")
    list_filter = ("is_staff",)
    search_fields = ("username", "email")
    ordering = ("id",)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeAdminForm

    list_display = (
        "id",
        "employee_number",
        "email",
        "phone",
        "role",
    )

    search_fields = (
        "employee_number",
        "user__email",
        "user__phone",
    )

    readonly_fields = ("employee_number",)

   
    def email(self, obj):
        return obj.user.email

    def phone(self, obj):
        return obj.user.phone

    def role(self, obj):
        group = obj.user.groups.first()
        return group.name if group else "-"

 
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            email = form.cleaned_data["email"]
            username = form.cleaned_data.get("username") or email.split("@")[0]
            phone = form.cleaned_data.get("phone")
            role = form.cleaned_data.get("role")
            is_active = form.cleaned_data.get("is_active", True)
            first_name = form.cleaned_data.get("first_name")
            last_name = form.cleaned_data.get("last_name")

            user = User.objects.create(
                email=email,
                username=username,
                phone=phone,
                is_active=is_active,
                password=make_password(form.cleaned_data["password"]),
                first_name=first_name,
                last_name=last_name,
            )

         
            group, _ = Group.objects.get_or_create(name=role)
            user.groups.add(group)
            obj.user = user

        super().save_model(request, obj, form, change)

        
@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    form = DoctorAdminForm
    list_display = (
        "id",
        "employee_number",
        "email",
        "phone",
        "specialization",
    )
    search_fields = ("employee__employee_number", "specialization")

    def employee_number(self, obj):
        return obj.employee.employee_number

    def email(self, obj):
        return obj.employee.user.email

    def phone(self, obj):
        return obj.employee.user.phone

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            email = form.cleaned_data["email"]
            username = form.cleaned_data.get("username") or email.split("@")[0]
            phone = form.cleaned_data.get("phone")
            specialization = form.cleaned_data.get("specialization")
            is_active = form.cleaned_data.get("is_active")
            first_name = form.cleaned_data.get("first_name")
            last_name = form.cleaned_data.get("last_name")

            user = User.objects.create(
                email=email,
                username=username,
                phone=phone,
                is_active=is_active,
                password=make_password(form.cleaned_data["password"]),
                first_name=first_name,
                last_name=last_name,
            )

            group, _ = Group.objects.get_or_create(name="doctor")
            user.groups.add(group)

            employee = Employee.objects.create(
                user=user,
                department_name="Doctor"
            )

            obj.employee = employee
            obj.specialization = specialization

        super().save_model(request, obj, form, change)



@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "created_at")
    readonly_fields = ("face_embedding",)



@admin.register(Camera)
class CameraAdmin(admin.ModelAdmin):
    list_display = ("id", "location_name", "status")
    list_filter = ("status",)
    search_fields = ("location_name",)



@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ("id", "patient__user__first_name", "status", "start_time", "end_time")
    list_filter = ("status",)
    date_hierarchy = "start_time"


@admin.register(EmotionResult)
class EmotionResultAdmin(admin.ModelAdmin):
    list_display = ("id", "session__id", "emotion", "percentage", "camera")
    list_filter = ("emotion", "camera", "session__id")



@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("id", "severity", "status", "created_at")
    list_filter = ("severity", "status")
    date_hierarchy = "created_at"



