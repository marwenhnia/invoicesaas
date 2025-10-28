from django.contrib import admin
from .models import Client, Invoice, InvoiceItem,UserProfile



@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'city', 'user', 'created_at')
    list_filter = ('country', 'city', 'created_at')
    search_fields = ('name', 'email', 'siret')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('user', 'name', 'email', 'phone')
        }),
        ('Adresse', {
            'fields': ('address', 'postal_code', 'city', 'country')
        }),
        ('Informations légales', {
            'fields': ('siret',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class InvoiceItemInline(admin.TabularInline):
    """Permet d'ajouter des lignes directement dans la facture"""
    model = InvoiceItem
    extra = 1
    fields = ('description', 'quantity', 'unit_price', 'total')
    readonly_fields = ('total',)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'client', 'issue_date', 'due_date', 'status', 'total', 'user')
    list_filter = ('status', 'issue_date', 'due_date')
    search_fields = ('invoice_number', 'client__name', 'client__email')
    readonly_fields = ('subtotal', 'tax_amount', 'total', 'created_at', 'updated_at', 'sent_at', 'paid_at')
    inlines = [InvoiceItemInline]
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('user', 'client', 'invoice_number', 'status')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'sent_at', 'paid_at')
        }),
        ('Montants', {
            'fields': ('tax_rate', 'subtotal', 'tax_amount', 'total')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['mark_as_sent', 'mark_as_paid']
    
    def mark_as_sent(self, request, queryset):
        for invoice in queryset:
            invoice.mark_as_sent()
        self.message_user(request, f"{queryset.count()} facture(s) marquée(s) comme envoyée(s).")
    mark_as_sent.short_description = "Marquer comme envoyée"
    
    def mark_as_paid(self, request, queryset):
        for invoice in queryset:
            invoice.mark_as_paid()
        self.message_user(request, f"{queryset.count()} facture(s) marquée(s) comme payée(s).")
    mark_as_paid.short_description = "Marquer comme payée"



@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'is_premium', 'trial_end_date', 'days_left')
    list_filter = ('is_premium', 'created_at')
    search_fields = ('user__username', 'company_name', 'siret')
    readonly_fields = ('created_at', 'updated_at', 'days_left')
    
    fieldsets = (
        ('Utilisateur', {
            'fields': ('user',)
        }),
        ('Informations freelance', {
            'fields': ('company_name', 'address', 'postal_code', 'city', 'country', 'siret', 'phone', 'logo')
        }),
        ('Abonnement', {
            'fields': ('is_premium', 'trial_end_date', 'stripe_customer_id', 'stripe_subscription_id')
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at', 'days_left'),
            'classes': ('collapse',)
        }),
    )
    
    def days_left(self, obj):
        """Affiche le nombre de jours restants"""
        if obj.is_premium:
            return "Premium actif ✅"
        days = obj.days_left_in_trial()
        if days > 0:
            return f"{days} jour(s) d'essai restant(s)"
        return "Essai terminé ⚠️"
    days_left.short_description = "Statut"
