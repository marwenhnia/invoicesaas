from celery import shared_task
from django.utils import timezone
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from .models import Invoice
from datetime import date


@shared_task
def check_overdue_invoices():
    """
    Tâche Celery qui vérifie les factures en retard et envoie des relances.
    Lance automatiquement tous les jours à 9h.
    """
    print("🔍 Vérification des factures en retard...")
    
    # Trouve toutes les factures envoyées dont la date d'échéance est dépassée
    overdue_invoices = Invoice.objects.filter(
        status='sent',
        due_date__lt=date.today()
    )
    
    count = 0
    for invoice in overdue_invoices:
        # Change le statut à "overdue"
        invoice.status = 'overdue'
        invoice.save()
        
        # Envoie l'email de relance
        if send_reminder_email(invoice):
            count += 1
            print(f"✅ Relance envoyée pour {invoice.invoice_number} à {invoice.client.email}")
        else:
            print(f"❌ Erreur d'envoi pour {invoice.invoice_number}")
    
    print(f"📊 Total : {count} relance(s) envoyée(s)")
    return f"{count} relance(s) envoyée(s)"


def send_reminder_email(invoice):
    """
    Envoie un email de relance pour une facture en retard.
    L'email part de FactureSnap mais le Reply-To est l'email de l'utilisateur.
    Retourne True si succès, False sinon.
    """
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.conf import settings
    from datetime import date
    
    try:
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
            from_email=settings.DEFAULT_FROM_EMAIL,  # no-reply@facturesnap.fr
            to=[invoice.client.email],
            reply_to=[invoice.user.email],  # ← L'email de l'utilisateur
        )
        
        email.content_subtype = 'html'  # Email en HTML
        email.send(fail_silently=False)
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de la relance : {e}")
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