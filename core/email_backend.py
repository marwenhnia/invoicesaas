"""
Backend email personnalisé utilisant l'API HTTP de Brevo
pour contourner les restrictions SMTP de Render Free.
"""
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import base64


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
        
        print(f"🔑 [BACKEND] BREVO_API_KEY accessible : {bool(settings.BREVO_API_KEY)}")
        if settings.BREVO_API_KEY:
            print(f"🔑 [BACKEND] Clé commence par : {settings.BREVO_API_KEY[:15]}...")
        else:
            print(f"❌ [BACKEND] settings.BREVO_API_KEY est VIDE !")
        return 0
        # Configure l'API Brevo avec la clé
        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key['api-key'] = settings.BREVO_API_KEY
        
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        
        num_sent = 0
        
        for message in email_messages:
            try:
                print(f"📧 [BREVO API] Envoi email : {message.subject}")
                print(f"📧 [BREVO API] From : {message.from_email}")
                print(f"📧 [BREVO API] To : {message.to}")
                
                # Parse l'email de l'expéditeur
                from_email = message.from_email
                if '<' in from_email:
                    # Format: "Name <email@example.com>"
                    from_name = from_email.split('<')[0].strip()
                    from_addr = from_email.split('<')[1].strip('>')
                else:
                    # Format: "email@example.com"
                    from_name = "FactureSnap"
                    from_addr = from_email
                
                # Prépare l'email
                send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
                    to=[{"email": recipient} for recipient in message.to],
                    sender={"name": from_name, "email": from_addr},
                    subject=message.subject,
                    html_content=message.body if message.content_subtype == 'html' else None,
                    text_content=message.body if message.content_subtype != 'html' else None,
                )
                
                # Ajoute Reply-To si présent
                if message.reply_to:
                    send_smtp_email.reply_to = {"email": message.reply_to[0]}
                
                # Ajoute les pièces jointes
                if message.attachments:
                    attachments = []
                    for filename, content, mimetype in message.attachments:
                        # Convertit bytes en base64
                        if isinstance(content, bytes):
                            content_b64 = base64.b64encode(content).decode('utf-8')
                        else:
                            content_b64 = base64.b64encode(content.encode()).decode('utf-8')
                        
                        attachments.append({
                            "name": filename,
                            "content": content_b64
                        })
                    send_smtp_email.attachment = attachments
                    print(f"📎 [BREVO API] {len(attachments)} pièce(s) jointe(s)")
                
                # Envoie l'email via l'API
                api_response = api_instance.send_transac_email(send_smtp_email)
                num_sent += 1
                
                print(f"✅ [BREVO API] Email envoyé ! Message ID: {api_response.message_id}")
                
            except ApiException as e:
                print(f"❌ [BREVO API] Erreur : {e}")
                if not self.fail_silently:
                    raise
            except Exception as e:
                print(f"❌ [BREVO API] Erreur inattendue : {e}")
                import traceback
                traceback.print_exc()
                if not self.fail_silently:
                    raise
        
        return num_sent