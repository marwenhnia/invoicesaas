from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from weasyprint import HTML
from .models import Invoice
from django.conf import settings
import traceback

def send_invoice_email(invoice):
    """
    Envoie la facture par email au client avec le PDF en pièce jointe.
    Envoi SYNCHRONE avec timeout pour éviter les blocages.
    Retourne True si succès, False sinon.
    """
    try:
        print(f"📧 Envoi email pour facture {invoice.invoice_number}")
        
        # Génère le PDF
        html_string = render_to_string('invoices/invoice_pdf.html', {'invoice': invoice})
        pdf_file = HTML(string=html_string).write_pdf()
        
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
        
        # Crée une connexion avec timeout
        from django.core.mail import get_connection
        connection = get_connection(
            timeout=30  # 30 secondes max
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
        
        # Attache le PDF
        email.attach(
            f'facture_{invoice.invoice_number}.pdf',
            pdf_file,
            'application/pdf'
        )
        
        # Envoie l'email
        email.send(fail_silently=False)
        
        print(f"✅ Email envoyé avec succès pour facture {invoice.invoice_number}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email : {e}")
        traceback.print_exc()
        return False