import os
from celery import Celery
from celery.schedules import crontab

# Définit le module de settings Django par défaut
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Crée l'instance Celery
app = Celery('invoicesnap')

# Charge la config depuis Django settings avec le namespace CELERY
app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover des tâches dans les apps Django
app.autodiscover_tasks()

# Configuration du planning (Celery Beat)
app.conf.beat_schedule = {
    'check-overdue-invoices-daily': {
        'task': 'core.tasks.check_overdue_invoices',
        'schedule': crontab(hour=9, minute=0),  # Tous les jours à 9h
    },
}

app.conf.timezone = 'Europe/Paris'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')