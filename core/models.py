from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator,MinValueValidator
from django.utils import timezone
from decimal import Decimal
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
class Client(models.Model):
    """
    Modèle représentant un client du freelance.
    Un utilisateur peut avoir plusieurs clients.
    """
    
    # Relation avec l'utilisateur
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='clients',
        verbose_name="Utilisateur"
    )
    
    # Informations de base
    name = models.CharField(
        max_length=200, 
        verbose_name="Nom du client"
    )
    
    email = models.EmailField(
        verbose_name="Email"
    )
    
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Le numéro doit être au format: '+999999999'. 9 à 15 chiffres."
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        null=True,
        verbose_name="Téléphone"
    )
    
    # Adresse (obligatoire pour factures françaises)
    address = models.TextField(
        verbose_name="Adresse"
    )
    
    postal_code = models.CharField(
        max_length=10,
        verbose_name="Code postal"
    )
    
    city = models.CharField(
        max_length=100,
        verbose_name="Ville"
    )
    
    country = models.CharField(
        max_length=100,
        default="France",
        verbose_name="Pays"
    )
    
    # Informations légales (optionnelles mais utiles)
    siret = models.CharField(
        max_length=14,
        blank=True,
        null=True,
        verbose_name="SIRET",
        help_text="Numéro SIRET (14 chiffres)"
    )
    
    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    
    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        ordering = ['-created_at']
        # Un user ne peut pas avoir 2 clients avec le même email
        unique_together = ['user', 'email']
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def get_full_address(self):
        """Retourne l'adresse complète formatée pour facture"""
        return f"{self.address}\n{self.postal_code} {self.city}\n{self.country}"
    


class Invoice(models.Model):
    """
    Modèle représentant une facture.
    """
    
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('sent', 'Envoyée'),
        ('paid', 'Payée'),
        ('overdue', 'En retard'),
        ('cancelled', 'Annulée'),
    ]
    
    # Relations
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='invoices',
        verbose_name="Utilisateur"
    )
    
    client = models.ForeignKey(
        Client,
        on_delete=models.PROTECT,  # Empêche de supprimer un client avec des factures
        related_name='invoices',
        verbose_name="Client"
    )
    
    # Informations facture
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name="Numéro de facture",
        help_text="Ex: INV-2024-001"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        verbose_name="Statut"
    )
    
    # Dates
    issue_date = models.DateField(
        default=timezone.now,
        verbose_name="Date d'émission"
    )
    
    due_date = models.DateField(
        verbose_name="Date d'échéance"
    )
    
    # Montants (calculés automatiquement depuis les lignes)
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Sous-total HT"
    )
    
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=20.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Taux de TVA (%)",
        help_text="Ex: 20.00 pour 20%"
    )
    
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Montant TVA"
    )
    
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total TTC"
    )
    
    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name="Notes",
        help_text="Conditions de paiement, mentions spéciales..."
    )
    
    # Métadonnées
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    
    sent_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date d'envoi"
    )
    
    paid_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Date de paiement"
    )
    
    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-issue_date', '-created_at']
    
    def __str__(self):
        return f"{self.invoice_number} - {self.client.name} ({self.get_status_display()})"
    
    def calculate_totals(self):
        """Calcule les totaux à partir des lignes de facture"""
        self.subtotal = sum(item.total for item in self.items.all())
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total = self.subtotal + self.tax_amount
        self.save()
    
    def is_overdue(self):
        """Vérifie si la facture est en retard"""
        if self.status in ['paid', 'cancelled']:
            return False
        return timezone.now().date() > self.due_date
    
    def mark_as_sent(self):
        """Marque la facture comme envoyée"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
    
    def mark_as_paid(self):
        """Marque la facture comme payée"""
        self.status = 'paid'
        self.paid_at = timezone.now()
        self.save()


class InvoiceItem(models.Model):
    """
    Modèle représentant une ligne de facture (prestation/produit).
    """
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Facture"
    )
    
    description = models.CharField(
        max_length=500,
        verbose_name="Description"
    )
    
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name="Quantité"
    )
    
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Prix unitaire HT"
    )
    
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Total HT"
    )
    
    class Meta:
        verbose_name = "Ligne de facture"
        verbose_name_plural = "Lignes de facture"
        ordering = ['id']
    
    def __str__(self):
        return f"{self.description} - {self.quantity} x {self.unit_price}€"
    
    def save(self, *args, **kwargs):
        """Calcule automatiquement le total avant de sauvegarder"""
        self.total = self.quantity * self.unit_price
        super().save(*args, **kwargs)
        # Recalcule les totaux de la facture parent
        self.invoice.calculate_totals()


class UserProfile(models.Model):
    """
    Profil étendu de l'utilisateur avec infos freelance et abonnement.
    """
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Informations freelance (pour les factures)
    company_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Nom de l'entreprise"
    )
    
    address = models.TextField(
        blank=True,
        verbose_name="Adresse"
    )
    
    postal_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name="Code postal"
    )
    
    city = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Ville"
    )
    
    country = models.CharField(
        max_length=100,
        default="France",
        verbose_name="Pays"
    )
    
    siret = models.CharField(
        max_length=14,
        blank=True,
        verbose_name="SIRET"
    )
    
    phone = models.CharField(
        max_length=17,
        blank=True,
        verbose_name="Téléphone"
    )
    
    logo = models.ImageField(
        upload_to='logos/',
        blank=True,
        null=True,
        verbose_name="Logo"
    )
    
    # Informations d'abonnement
    is_premium = models.BooleanField(
        default=False,
        verbose_name="Abonnement Premium actif"
    )
    
    trial_end_date = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fin de la période d'essai"
    )
    
    stripe_customer_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID Client Stripe"
    )
    
    stripe_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="ID Abonnement Stripe"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Date de création"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Dernière modification"
    )
    
    class Meta:
        verbose_name = "Profil utilisateur"
        verbose_name_plural = "Profils utilisateurs"
    
    def __str__(self):
        return f"Profil de {self.user.username}"
    
    def is_trial_active(self):
        """Vérifie si l'essai gratuit est encore actif"""
        if not self.trial_end_date:
            return False
        from django.utils import timezone
        return timezone.now() <= self.trial_end_date
    
    def can_access_app(self):
        """Vérifie si l'utilisateur peut accéder à l'application"""
        return self.is_premium or self.is_trial_active()
    
    def days_left_in_trial(self):
        """Retourne le nombre de jours restants dans l'essai"""
        if not self.trial_end_date:
            return 0
        from django.utils import timezone
        delta = self.trial_end_date - timezone.now()
        return max(0, delta.days)
    
    def minutes_left_in_trial(self):
        """Retourne le nombre de minutes restantes (pour les tests)"""
        if not self.trial_end_date:
            return 0
        from django.utils import timezone
        delta = self.trial_end_date - timezone.now()
        return max(0, int(delta.total_seconds() / 60))




#@receiver(post_save, sender=User)
#def save_user_profile(sender, instance, **kwargs):
   # """Sauvegarde le profil quand le user est sauvegardé"""
    #if hasattr(instance, 'profile'):
        #instance.profile.save()



# Trouve cette fonction et modifie-la
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Crée automatiquement un profil lors de la création d'un utilisateur"""
    if created:
        # PRODUCTION : 30 jours d'essai
        trial_end = timezone.now() + timedelta(days=30)
        
        # get_or_create évite les doublons
        UserProfile.objects.get_or_create(
            user=instance,
            defaults={
                'trial_end_date': trial_end
            }
        )