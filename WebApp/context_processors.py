# WebApp/context_processors.py

from WebApp.models import Preschooler

def pending_validation_count(request):
    if request.user.is_authenticated:
        count = Preschooler.objects.filter(status='pending').count()
    else:
        count = 0
    return {'pending_validation_count': count}
