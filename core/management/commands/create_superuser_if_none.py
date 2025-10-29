from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os

class Command(BaseCommand):
    help = 'Crée un superuser si aucun n\'existe'

    def handle(self, *args, **options):
        if not User.objects.filter(is_superuser=True).exists():
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
            email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@facturesnap.fr')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'changeme123')
            
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            
            self.stdout.write(self.style.SUCCESS(f'✅ Superuser "{username}" créé avec succès !'))
        else:
            self.stdout.write(self.style.WARNING('⚠️ Un superuser existe déjà.'))