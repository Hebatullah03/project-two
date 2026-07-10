from core.models import Alert
from core.models import User

def active_alerts_processor(request):
    if not request.user.is_authenticated:
        return {}

    count = 0
    if request.user.groups.filter(name=User.Role.DOCTOR).exists():
        count = Alert.objects.filter(
            session__patient__doctor__employee__user=request.user, 
            status__in=[Alert.Status.TRIGGERED, Alert.Status.ACKNOWLEDGED]
        ).count()
    elif request.user.groups.filter(name=User.Role.RECEPTIONIST).exists():
        count = Alert.objects.filter(
            status__in=[Alert.Status.TRIGGERED, Alert.Status.ACKNOWLEDGED]
        ).count()

    return {'active_alerts_count': count}
