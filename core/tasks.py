from celery import shared_task
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from .models import Invoice
from datetime import date

from django.conf import settings
from weasyprint import HTML
import traceback
import gc


@shared_task
def check_overdue_invoices():
    """
    Tâche périodique : vérifie les factures en retard et envoie des relances.
    À exécuter quotidiennement via Celery Beat.
    """
    from core.models import Invoice
    from datetime import date
    
    print("🔍 [CELERY BEAT] Vérification des factures en retard...")
    
    # Récupère toutes les factures en retard et impayées
    overdue_invoices = Invoice.objects.filter(
        status='unpaid',
        due_date__lt=date.today()
    )
    
    count = 0
    for invoice in overdue_invoices:
        # Lance l'envoi de relance en arrière-plan
        send_reminder_email_task.delay(invoice.id)
        count += 1
    
    print(f"✅ [CELERY BEAT] {count} relance(s) programmée(s)")
    
    return f"{count} relances envoyées"


def send_reminder_email(invoice):
    """
    Envoie un email de relance pour une facture en retard.
    Envoi SYNCHRONE.
    Retourne True si succès, False sinon.
    """
    from datetime import date
    
    try:
        print(f"⚠️ Envoi relance pour facture {invoice.invoice_number}")
        
        # Calcule le nombre de jours de retard
        days_overdue = (date.today() - invoice.due_date).days
        
        # Prépare l'email HTML
        email_html = render_to_string('emails/reminder_email.html', {
            'client_name': invoice.client.name,
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date.strftime('%d/%m/%Y'),
            'due_date': invoice.due_date.strftime('%d/%m/%Y'),
            'days_overdue': days_overdue,
            'total': invoice.total,
            'freelance_name': invoice.user.get_full_name() or invoice.user.username,
            'freelance_email': invoice.user.email,
        })
        
        # Crée l'email
        subject = f'⚠️ Relance - Facture {invoice.invoice_number} en attente de paiement'
        
        # Crée une connexion avec timeout
        from django.core.mail import get_connection
        connection = get_connection(
            timeout=30
        )
        
        email = EmailMessage(
            subject=subject,
            body=email_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invoice.client.email],
            reply_to=[invoice.user.email],
            connection=connection
        )
        
        email.content_subtype = 'html'
        email.send(fail_silently=False)
        
        print(f"✅ Relance envoyée pour facture {invoice.invoice_number}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de la relance : {e}")
        traceback.print_exc()
        return False

    """
    Tâche Celery pour envoyer un email de relance en arrière-plan.
    """
    from core.models import Invoice
    from datetime import date
    
    try:
        print(f"⚠️ [CELERY] Début envoi relance pour facture ID={invoice_id}")
        
        # Récupère la facture
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Calcule le nombre de jours de retard
        days_overdue = (date.today() - invoice.due_date).days
        
        # Prépare l'email HTML
        email_html = render_to_string('emails/reminder_email.html', {
            'client_name': invoice.client.name,
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date.strftime('%d/%m/%Y'),
            'due_date': invoice.due_date.strftime('%d/%m/%Y'),
            'days_overdue': days_overdue,
            'total': invoice.total,
            'freelance_name': invoice.user.get_full_name() or invoice.user.username,
            'freelance_email': invoice.user.email,
        })
        
        # Crée l'email
        subject = f'⚠️ Relance - Facture {invoice.invoice_number} en attente de paiement'
        
        email = EmailMessage(
            subject=subject,
            body=email_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invoice.client.email],
            reply_to=[invoice.user.email],
        )
        
        email.content_subtype = 'html'
        email.send(fail_silently=False)
        
        print(f"✅ [CELERY] Relance envoyée pour facture {invoice.invoice_number}")
        
        return f"Relance envoyée pour facture {invoice.invoice_number}"
        
    except Invoice.DoesNotExist:
        print(f"❌ [CELERY] Facture {invoice_id} introuvable")
        return f"Facture {invoice_id} introuvable"
        
    except Exception as e:
        print(f"❌ [CELERY] Erreur : {e}")
        traceback.print_exc()
        
        # Réessaie jusqu'à 3 fois
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))