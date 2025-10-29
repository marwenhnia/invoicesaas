from celery import shared_task
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from .models import Invoice
from datetime import date

from django.conf import settings
from weasyprint import HTML
import traceback


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
    Lance l'envoi de relance en arrière-plan via Celery.
    """
    from core.tasks import send_reminder_email_task
    
    try:
        send_reminder_email_task.delay(invoice.id)
        print(f"✅ Tâche de relance lancée pour facture {invoice.invoice_number}")
        return True
    except Exception as e:
        print(f"❌ Erreur lors du lancement de la tâche : {e}")
        return False


@shared_task
def send_invoice_async(invoice_id):
    """
    Tâche asynchrone pour envoyer une facture par email.
    Utilisée pour ne pas bloquer l'interface utilisateur.
    """
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        from .utils import send_invoice_email
        return send_invoice_email(invoice)
    except Invoice.DoesNotExist:
        return False
    





@shared_task(bind=True, max_retries=3)
def send_invoice_email_task(self, invoice_id):
    """
    Tâche Celery pour envoyer une facture par email en arrière-plan.
    """
    from core.models import Invoice
    
    try:
        print(f"📧 [CELERY] Début envoi email pour facture ID={invoice_id}")
        
        # Récupère la facture
        invoice = Invoice.objects.get(id=invoice_id)
        
        # Génère le PDF
        html_string = render_to_string('invoices/invoice_pdf.html', {'invoice': invoice})
        pdf_file = HTML(string=html_string).write_pdf()
        print(f"✅ [CELERY] PDF généré")
        
        # Prépare l'email HTML
        email_html = render_to_string('emails/invoice_email.html', {
            'client_name': invoice.client.name,
            'invoice_number': invoice.invoice_number,
            'issue_date': invoice.issue_date.strftime('%d/%m/%Y'),
            'due_date': invoice.due_date.strftime('%d/%m/%Y'),
            'subtotal': invoice.subtotal,
            'tax_rate': invoice.tax_rate,
            'tax_amount': invoice.tax_amount,
            'total': invoice.total,
            'notes': invoice.notes,
            'freelance_name': invoice.user.get_full_name() or invoice.user.username,
            'freelance_email': invoice.user.email,
        })
        
        # Crée l'email
        subject = f'Facture {invoice.invoice_number} - {invoice.client.name}'
        
        email = EmailMessage(
            subject=subject,
            body=email_html,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[invoice.client.email],
            reply_to=[invoice.user.email],
        )
        
        email.content_subtype = 'html'
        
        # Attache le PDF
        email.attach(
            f'facture_{invoice.invoice_number}.pdf',
            pdf_file,
            'application/pdf'
        )
        
        print(f"📤 [CELERY] Envoi email...")
        
        # Envoie l'email
        email.send(fail_silently=False)
        
        print(f"✅ [CELERY] Email envoyé avec succès pour facture {invoice.invoice_number}")
        
        return f"Email envoyé pour facture {invoice.invoice_number}"
        
    except Invoice.DoesNotExist:
        print(f"❌ [CELERY] Facture {invoice_id} introuvable")
        return f"Facture {invoice_id} introuvable"
        
    except Exception as e:
        print(f"❌ [CELERY] Erreur : {e}")
        traceback.print_exc()
        
        # Réessaie jusqu'à 3 fois avec délai exponentiel
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_reminder_email_task(self, invoice_id):
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