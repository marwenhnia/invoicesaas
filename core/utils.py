from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from weasyprint import HTML
from .models import Invoice


def send_invoice_email(invoice):
    """
    Lance l'envoi d'email en arrière-plan via Celery.
    Retourne True immédiatement (l'email sera envoyé de manière asynchrone).
    """
    from core.tasks import send_invoice_email_task
    
    try:
        # Lance la tâche Celery en arrière-plan
        send_invoice_email_task.delay(invoice.id)
        print(f"✅ Tâche d'envoi email lancée pour facture {invoice.invoice_number}")
        return True
    except Exception as e:
        print(f"❌ Erreur lors du lancement de la tâche : {e}")
        return False