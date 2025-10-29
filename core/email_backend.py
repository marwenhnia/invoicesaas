"""
Backend email personnalisé utilisant l'API HTTP de Brevo
pour contourner les restrictions SMTP de Render Free.
"""
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException


class BrevoAPIBackend(BaseEmailBackend):
    """
    Backend email utilisant l'API Brevo au lieu de SMTP.
    """
    
    def send_messages(self, email_messages):
        """
        Envoie les emails via l'API Brevo.
        """
        if not email_messages:
            return 0
        
        # Configure l'API Brevo
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = settings.BREVO_API_KEY
        
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        
        num_sent = 0
        
        for message in email_messages:
            try:
                # Prépare l'email
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=[{"email": recipient} for recipient in message.to],
                    sender={"email": message.from_email.split('<')[-1].strip('>')},
                    subject=message.subject,
                    html_content=message.body if message.content_subtype == 'html' else None,
                    text_content=message.body if message.content_subtype != 'html' else None,
                    reply_to={"email": message.reply_to[0]} if message.reply_to else None,
                )
                
                # Ajoute les pièces jointes
                if message.attachments:
                    attachments = []
                    for filename, content, mimetype in message.attachments:
                        import base64
                        attachments.append({
                            "name": filename,
                            "content": base64.b64encode(content).decode('utf-8')
                        })
                    send_smtp_email.attachment = attachments
                
                # Envoie l'email via l'API
                api_instance.send_transac_email(send_smtp_email)
                num_sent += 1
                
                print(f"✅ Email envoyé via API Brevo : {message.subject}")
                
            except ApiException as e:
                print(f"❌ Erreur API Brevo : {e}")
                if not self.fail_silently:
                    raise
        
        return num_sent