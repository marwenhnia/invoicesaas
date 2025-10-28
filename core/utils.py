from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from weasyprint import HTML
from .models import Invoice


def send_invoice_email(invoice):
    """
    Envoie la facture par email au client avec le PDF en pièce jointe.
    Retourne True si succès, False sinon.
    """
    try:
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
        
        email = EmailMessage(
            subject=subject,
            body=email_html,
            to=[invoice.client.email],
            reply_to=[invoice.user.email],
        )
        
        email.content_subtype = 'html'  # Email en HTML
        
        # Attache le PDF
        email.attach(
            f'facture_{invoice.invoice_number}.pdf',
            pdf_file,
            'application/pdf'
        )
        
        # Envoie l'email
        email.send(fail_silently=False)
        
        return True
        
    except Exception as e:
        print(f"Erreur lors de l'envoi de l'email : {e}")
        return False