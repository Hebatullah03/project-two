import pytest


@pytest.fixture
def doctor_group(db):
    """Create or get doctor group."""
    from django.contrib.auth.models import Group
    from core.models import User
    return Group.objects.get_or_create(name=User.Role.DOCTOR)[0]


@pytest.fixture
def receptionist_group(db):
    """Create or get receptionist group."""
    from django.contrib.auth.models import Group
    from core.models import User
    return Group.objects.get_or_create(name=User.Role.RECEPTIONIST)[0]


@pytest.fixture
def doctor_user(db, doctor_group):
    """Create a test doctor user."""
    from core.models import User
    
    u = User.objects.create_user(
        username="doc@test.com",
        email="doc@test.com",
        password="testpass123",
        first_name="Ahmed",
        last_name="Khalil"
    )
    u.groups.add(doctor_group)
    return u


@pytest.fixture
def receptionist_user(db, receptionist_group):
    """Create a test receptionist user."""
    from core.models import User
    u = User.objects.create_user(
        username="rec@test.com",
        email="rec@test.com",
        password="testpass123",
        first_name="Sara",
        last_name="Ali"
    )
    u.groups.add(receptionist_group)
    return u


@pytest.fixture
def doctor(db, doctor_user):
    """Create a test doctor."""
    from core.models import Employee, Doctor
    employee = Employee.objects.create(user=doctor_user)
    return Doctor.objects.create(employee=employee)
