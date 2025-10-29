from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse,JsonResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string
from django.contrib import messages
from weasyprint import HTML
from .models import Invoice, Client,UserProfile
from django.db.models import Count, Q
from django.utils import timezone
from .forms import InvoiceForm, InvoiceItemFormSet, ClientForm,UserForm, UserProfileForm
from .utils import send_invoice_email
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView
from .forms import SignUpForm, LoginForm
from django.urls import reverse
import stripe
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
import json
from core.decorators import admin_required
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
import os
stripe.api_key = settings.STRIPE_SECRET_KEY
from django.urls import reverse_lazy

@login_required
def dashboard(request):
    """Dashboard principal avec liste des factures"""
    
    # Récupère les factures de l'utilisateur
    invoices = Invoice.objects.filter(user=request.user).select_related('client')
    
    # Filtre par statut si demandé
    status_filter = request.GET.get('status')
    if status_filter:
        invoices = invoices.filter(status=status_filter)
    
    # Calcul des stats
    stats = {
        'total': Invoice.objects.filter(user=request.user).count(),
        'paid': Invoice.objects.filter(user=request.user, status='paid').count(),
        'sent': Invoice.objects.filter(user=request.user, status='sent').count(),
        'overdue': Invoice.objects.filter(user=request.user, status='overdue').count(),
    }
    
    context = {
        'invoices': invoices,
        'stats': stats,
    }
    
    return render(request, 'core/dashboard.html', context)


@login_required
def generate_invoice_pdf(request, invoice_id):
    """Génère un PDF pour une facture donnée"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    
    html_string = render_to_string('invoices/invoice_pdf.html', {'invoice': invoice})
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="facture_{invoice.invoice_number}.pdf"'
    
    return response


@login_required
def invoice_detail(request, invoice_id):
    """Affiche les détails d'une facture"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    return render(request, 'core/invoice_detail.html', {'invoice': invoice})


@login_required
def invoice_mark_paid(request, invoice_id):
    """Marque une facture comme payée"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    invoice.mark_as_paid()
    messages.success(request, f'Facture {invoice.invoice_number} marquée comme payée !')
    return redirect('core:dashboard')


@login_required
def invoice_create(request):
    """Crée une nouvelle facture"""
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, user=request.user)
        formset = InvoiceItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            invoice = form.save(commit=False)
            invoice.user = request.user
            
            # Définit le statut selon le bouton cliqué
            status = request.POST.get('status', 'draft')
            invoice.status = status
            
            invoice.save()
            
            # Sauvegarde les lignes de facture
            formset.instance = invoice
            formset.save()
            
            # Recalcule les totaux
            invoice.calculate_totals()
            
            # Si "Enregistrer et marquer comme envoyée" → envoie l'email
            if status == 'sent':
                from .utils import send_invoice_email
                
                if send_invoice_email(invoice):
                    invoice.mark_as_sent()
                    messages.success(
                        request, 
                        f'✅ Facture {invoice.invoice_number} créée et envoyée par email à {invoice.client.email} !'
                    )
                else:
                    # L'email n'a pas pu être envoyé, garde en brouillon
                    invoice.status = 'draft'
                    invoice.save()
                    messages.warning(
                        request, 
                        f'⚠️ Facture {invoice.invoice_number} créée mais l\'email n\'a pas pu être envoyé. Vérifiez votre configuration email.'
                    )
            else:
                messages.success(request, f'✅ Facture {invoice.invoice_number} enregistrée comme brouillon.')
            
            return redirect('core:dashboard')
    else:
        form = InvoiceForm(user=request.user)
        formset = InvoiceItemFormSet()
    
    context = {
        'form': form,
        'formset': formset,
        'title': 'Nouvelle facture',
    }
    
    return render(request, 'core/invoice_form.html', context)

@login_required
def client_list(request):
    """Liste des clients"""
    clients = Client.objects.filter(user=request.user).annotate(
        invoice_count=Count('invoices')
    )
    return render(request, 'core/client_list.html', {'clients': clients})

@login_required
def client_create(request):
    """Crée un nouveau client"""
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save(commit=False)
            client.user = request.user
            client.save()
            messages.success(request, f'Client {client.name} créé avec succès !')
            return redirect('core:client_list')
    else:
        form = ClientForm()
    
    return render(request, 'core/client_form.html', {'form': form, 'title': 'Nouveau client'})

@login_required
def client_edit(request, client_id):
    """Modifie un client"""
    client = get_object_or_404(Client, id=client_id, user=request.user)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save()
            messages.success(request, f'Client {client.name} mis à jour !')
            return redirect('core:client_list')
    else:
        form = ClientForm(instance=client)
    
    return render(request, 'core/client_form.html', {'form': form, 'title': f'Modifier {client.name}'})


@login_required
def client_detail(request, client_id):
    """Affiche les détails d'un client"""
    client = get_object_or_404(Client, id=client_id, user=request.user)
    invoices = client.invoices.all()[:10]  # 10 dernières factures
    return render(request, 'core/client_detail.html', {'client': client, 'invoices': invoices})

@login_required
def invoice_edit(request, invoice_id):
    """Modifie une facture existante"""
    
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST, instance=invoice, user=request.user)
        formset = InvoiceItemFormSet(request.POST, instance=invoice)
        
        if form.is_valid() and formset.is_valid():
            old_status = invoice.status
            invoice = form.save()
            formset.save()
            invoice.calculate_totals()
            
            # Si passage de brouillon à envoyée → envoie l'email
            new_status = request.POST.get('status')
            if new_status == 'sent' and old_status == 'draft':
                from .utils import send_invoice_email
                
                if send_invoice_email(invoice):
                    invoice.mark_as_sent()
                    messages.success(
                        request, 
                        f'✅ Facture {invoice.invoice_number} mise à jour et envoyée par email à {invoice.client.email} !'
                    )
                else:
                    messages.warning(
                        request, 
                        f'⚠️ Facture {invoice.invoice_number} mise à jour mais l\'email n\'a pas pu être envoyé.'
                    )
            else:
                messages.success(request, f'✅ Facture {invoice.invoice_number} mise à jour !')
            
            return redirect('core:dashboard')
    else:
        form = InvoiceForm(instance=invoice, user=request.user)
        formset = InvoiceItemFormSet(instance=invoice)
    
    context = {
        'form': form,
        'formset': formset,
        'title': f'Modifier {invoice.invoice_number}',
        'invoice': invoice,
    }
    
    return render(request, 'core/invoice_form.html', context)

@login_required
def invoice_mark_sent(request, invoice_id):
    """Marque une facture comme envoyée ET l'envoie par email"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    
    # Envoie l'email
    if send_invoice_email(invoice):
        invoice.mark_as_sent()
        messages.success(request, f'Facture {invoice.invoice_number} envoyée par email à {invoice.client.email} !')
    else:
        messages.error(request, f'Erreur lors de l\'envoi de l\'email. Vérifiez votre configuration email.')
    
    return redirect('core:invoice_detail', invoice_id=invoice.id)

@login_required
def invoice_send_email(request, invoice_id):
    """Envoie la facture par email sans changer le statut"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    
    if send_invoice_email(invoice):
        messages.success(request, f'Facture {invoice.invoice_number} envoyée par email à {invoice.client.email} !')
    else:
        messages.error(request, 'Erreur lors de l\'envoi de l\'email. Vérifiez votre configuration.')
    
    return redirect('core:invoice_detail', invoice_id=invoice.id)

@login_required
def invoice_delete(request, invoice_id):
    """Supprime une facture"""
    invoice = get_object_or_404(Invoice, id=invoice_id, user=request.user)
    invoice_number = invoice.invoice_number
    invoice.delete()
    messages.success(request, f'Facture {invoice_number} supprimée !')
    return redirect('core:dashboard')



@login_required
def user_settings(request):
    """Page de paramètres utilisateur"""
    
    # Assure qu'un profil existe (normalement créé automatiquement)
    if not hasattr(request.user, 'profile'):
        from datetime import timedelta
        UserProfile.objects.create(
            user=request.user,
            trial_end_date=timezone.now().date() + timedelta(days=30)
        )
    
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=request.user.profile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Vos paramètres ont été mis à jour avec succès !')
            return redirect('core:settings')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=request.user.profile)
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
    }
    
    return render(request, 'core/settings.html', context)


@login_required
def upgrade_to_premium(request):
    """Page pour passer à Premium (on implémentera Stripe après)"""
    
    context = {
        'trial_days_left': request.user.profile.days_left_in_trial(),
        'is_trial_active': request.user.profile.is_trial_active(),
    }
    
    return render(request, 'core/upgrade.html', context)



def landing_page(request):
    """Page d'accueil publique"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return render(request, 'landing.html')



def signup_view(request):
    """Vue d'inscription"""
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Connecte automatiquement l'utilisateur après inscription
            login(request, user)
            messages.success(request, f'Bienvenue {user.first_name} ! Votre essai gratuit de 30 jours commence maintenant 🎉')
            return redirect('core:dashboard')
    else:
        form = SignUpForm()
    
    return render(request, 'auth/signup.html', {'form': form})

class CustomLoginView(LoginView):
    """
    Vue de login personnalisée avec redirection intelligente.
    """
    template_name = 'auth/login.html'
    
    def get_success_url(self):
        """
        Redirige les admin vers /admin-dashboard/
        et les users normaux vers /app/
        """
        user = self.request.user
        
        # Vérifie que l'user est bien chargé
        if not user or not user.is_authenticated:
            return reverse_lazy('core:dashboard')
        
        # Si admin → dashboard admin
        if user.is_staff or user.is_superuser:
            return reverse_lazy('admin_dashboard')
        
        # Sinon → dashboard user
        return reverse_lazy('core:dashboard')
    

from django.contrib.auth import logout


@login_required
def logout_view(request):
    """Déconnexion de l'utilisateur"""
    logout(request)
    messages.success(request, 'Vous avez été déconnecté avec succès.')
    return redirect('landing')


@login_required
def client_detail(request, client_id):
    """Affiche les détails d'un client"""
    client = get_object_or_404(Client, id=client_id, user=request.user)
    invoices = client.invoices.all().order_by('-issue_date')
    
    # Statistiques
    paid_count = invoices.filter(status='paid').count()
    pending_count = invoices.filter(status__in=['sent', 'overdue']).count()
    
    context = {
        'client': client,
        'invoices': invoices,
        'paid_count': paid_count,
        'pending_count': pending_count,
    }
    return render(request, 'core/client_detail.html', context)

@login_required
def client_delete(request, client_id):
    """Supprime un client"""
    client = get_object_or_404(Client, id=client_id, user=request.user)
    client_name = client.name
    
    # Vérifie si le client a des factures
    if client.invoices.exists():
        messages.error(request, f'Impossible de supprimer {client_name} : ce client a des factures.')
        return redirect('core:client_detail', client_id=client.id)
    
    client.delete()
    messages.success(request, f'Client {client_name} supprimé avec succès !')
    return redirect('core:client_list')



@login_required
def create_checkout_session(request):
    """Crée une session de paiement Stripe Checkout"""
    
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=request.user.email,
            payment_method_types=['card'],
            line_items=[{
                'price': settings.STRIPE_PRICE_ID,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=settings.SITE_URL + '/app/payment-success/?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=settings.SITE_URL + '/app/upgrade/',
            metadata={
                'user_id': request.user.id,
            }
        )
        
        return redirect(checkout_session.url)
        
    except Exception as e:
        messages.error(request, f'Erreur lors de la création de la session de paiement : {str(e)}')
        return redirect('core:upgrade')


@login_required
def payment_success(request):
    """Page affichée après un paiement réussi"""
    session_id = request.GET.get('session_id')
    
    if session_id:
        try:
            # Récupère la session Stripe
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Active le compte premium
            profile = request.user.profile
            profile.is_premium = True
            profile.stripe_customer_id = session.customer
            profile.stripe_subscription_id = session.subscription
            profile.save()
            
            messages.success(request, '🎉 Félicitations ! Votre compte Premium est maintenant actif !')
            
        except Exception as e:
            messages.error(request, f'Erreur lors de la validation du paiement : {str(e)}')
    
    return render(request, 'core/payment_success.html')


@csrf_exempt
def stripe_webhook(request):
    """Webhook pour recevoir les événements Stripe"""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)
    
    # Gère les différents types d'événements
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        handle_checkout_session(session)
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        handle_subscription_cancelled(subscription)
    
    elif event['type'] == 'invoice.payment_failed':
        invoice = event['data']['object']
        handle_payment_failed(invoice)
    
    return HttpResponse(status=200)


def handle_checkout_session(session):
    """Traite un paiement réussi"""
    user_id = session['metadata'].get('user_id')
    
    if user_id:
        try:
            from django.contrib.auth.models import User
            user = User.objects.get(id=user_id)
            profile = user.profile
            
            profile.is_premium = True
            profile.stripe_customer_id = session['customer']
            profile.stripe_subscription_id = session['subscription']
            profile.save()
            
            print(f"✅ Compte Premium activé pour {user.username}")
            
        except User.DoesNotExist:
            print(f"❌ Utilisateur {user_id} introuvable")


def handle_subscription_cancelled(subscription):
    """Traite l'annulation d'un abonnement"""
    try:
        profile = UserProfile.objects.get(stripe_subscription_id=subscription['id'])
        profile.is_premium = False
        profile.save()
        
        print(f"❌ Abonnement annulé pour {profile.user.username}")
        
    except UserProfile.DoesNotExist:
        print(f"❌ Profil introuvable pour l'abonnement {subscription['id']}")


def handle_payment_failed(invoice):
    """Traite un paiement échoué"""
    customer_id = invoice['customer']
    
    try:
        profile = UserProfile.objects.get(stripe_customer_id=customer_id)
        # Tu peux envoyer un email de rappel ici
        print(f"⚠️ Paiement échoué pour {profile.user.username}")
        
    except UserProfile.DoesNotExist:
        print(f"❌ Profil introuvable pour le client {customer_id}")


@login_required
def cancel_subscription(request):
    """Annule l'abonnement d'un utilisateur"""
    profile = request.user.profile
    
    if profile.stripe_subscription_id:
        try:
            stripe.Subscription.delete(profile.stripe_subscription_id)
            
            profile.is_premium = False
            profile.stripe_subscription_id = ''
            profile.save()
            
            messages.success(request, 'Votre abonnement a été annulé avec succès.')
            
        except Exception as e:
            messages.error(request, f'Erreur lors de l\'annulation : {str(e)}')
    
    return redirect('core:settings')



def robots_txt(request):
    content = """User-agent: *
Allow: /
Disallow: /app/
Disallow: /admin/

Sitemap: https://myjunkfuel.com/sitemap.xml"""
    return HttpResponse(content, content_type="text/plain")


def sitemap_xml(request):
    xml = render_to_string('sitemap.xml')
    return HttpResponse(xml, content_type="application/xml")

@admin_required
def admin_dashboard(request):
    """
    Dashboard admin avec statistiques globales.
    """
    # Statistiques utilisateurs
    total_users = User.objects.count()
    premium_users = UserProfile.objects.filter(subscription_status='active').count()
    free_users = total_users - premium_users
    
    # Statistiques financières
    total_revenue = premium_users * 9
    
    # Statistiques factures
    total_invoices = Invoice.objects.count()
    paid_invoices = Invoice.objects.filter(status='paid').count()
    unpaid_invoices = Invoice.objects.filter(status='unpaid').count()
    
    # Nouveaux utilisateurs (7 derniers jours)
    last_week = timezone.now() - timedelta(days=7)
    new_users_week = User.objects.filter(date_joined__gte=last_week).count()
    
    # Utilisateurs actifs (ayant créé une facture dans les 30 derniers jours)
    last_month = timezone.now() - timedelta(days=30)
    active_users = User.objects.filter(
        invoice__created_at__gte=last_month
    ).distinct().count()
    
    # Top 5 utilisateurs (par nombre de factures)
    top_users = User.objects.annotate(
        invoice_count=Count('invoice')
    ).order_by('-invoice_count')[:5]
    
    context = {
        'total_users': total_users,
        'premium_users': premium_users,
        'free_users': free_users,
        'total_revenue': total_revenue,
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'unpaid_invoices': unpaid_invoices,
        'new_users_week': new_users_week,
        'active_users': active_users,
        'top_users': top_users,
    }
    
    return render(request, 'admin/dashboard.html', context)


@admin_required
def admin_users_list(request):
    """
    Liste de tous les utilisateurs avec filtres.
    """
    # Récupère tous les utilisateurs
    users = User.objects.select_related('profile').annotate(
        invoice_count=Count('invoice'),
        total_revenue=Count('invoice', filter=Q(invoice__status='paid'))
    ).order_by('-date_joined')
    
    # Filtres
    status_filter = request.GET.get('status', 'all')
    search = request.GET.get('search', '')
    
    if status_filter == 'premium':
        users = users.filter(profile__subscription_status='active')
    elif status_filter == 'free':
        users = users.exclude(profile__subscription_status='active')
    elif status_filter == 'trial':
        users = users.filter(profile__subscription_status='trialing')
    
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    context = {
        'users': users,
        'status_filter': status_filter,
        'search': search,
        'total_count': users.count(),
    }
    
    return render(request, 'admin/users_list.html', context)

@admin_required
def admin_user_detail(request, user_id):
    """
    Détails d'un utilisateur spécifique.
    """
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    
    # Statistiques de l'utilisateur
    invoices = Invoice.objects.filter(user=user).order_by('-created_at')
    clients = Client.objects.filter(user=user)
    
    total_invoices = invoices.count()
    paid_invoices = invoices.filter(status='paid').count()
    unpaid_invoices = invoices.filter(status='unpaid').count()
    
    context = {
        'user_obj': user,
        'profile': profile,
        'invoices': invoices[:10],
        'clients': clients,
        'total_invoices': total_invoices,
        'paid_invoices': paid_invoices,
        'unpaid_invoices': unpaid_invoices,
    }
    
    return render(request, 'admin/user_detail.html', context)


@admin_required
def admin_toggle_subscription(request, user_id):
    """
    Active/désactive manuellement l'abonnement d'un utilisateur.
    """
    if request.method != 'POST':
        return redirect('admin_users_list')
    
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    
    if profile.subscription_status == 'active':
        profile.subscription_status = 'inactive'
        profile.stripe_subscription_id = None
        profile.save()
        messages.success(request, f"✅ {user.username} est maintenant en plan Free.")
    else:
        profile.subscription_status = 'active'
        profile.subscription_start_date = timezone.now()
        profile.save()
        messages.success(request, f"✅ {user.username} est maintenant en plan Premium.")
    
    return redirect('admin_user_detail', user_id=user_id)

def create_superuser_endpoint(request):
    """
    Endpoint temporaire pour créer un superuser.
    À SUPPRIMER après utilisation !
    """
    # Sécurité basique
    secret = request.GET.get('secret')
    if secret != os.environ.get('SUPERUSER_SECRET', 'change-me-secret-123'):
        return HttpResponse("❌ Accès refusé", status=403)
    
    # Vérifie si un superuser existe déjà
    if User.objects.filter(is_superuser=True).exists():
        return HttpResponse("⚠️ Un superuser existe déjà !", status=400)
    
    # Crée le superuser
    username = request.GET.get('username', 'facturesnapadmin')
    email = request.GET.get('email', 'info@myjunfuel.com')
    password = request.GET.get('password', 'A7mara5thar095*')
    
    user = User.objects.create_superuser(
        username=username,
        email=email,
        password=password
    )
    
    return HttpResponse(f"✅ Superuser '{username}' créé avec succès ! Email: {email} | SUPPRIME CET ENDPOINT MAINTENANT !")



def check_superusers(request):
    """
    Liste tous les superusers.
    À SUPPRIMER après vérification !
    """
    from django.contrib.auth.models import User
    
    superusers = User.objects.filter(is_superuser=True)
    
    if not superusers.exists():
        return HttpResponse("❌ Aucun superuser n'existe !")
    
    result = "<h1>Liste des Superusers :</h1>"
    for user in superusers:
        result += f"<p>Username: <strong>{user.username}</strong> | Email: {user.email} | Staff: {user.is_staff} | Superuser: {user.is_superuser}</p>"
    
    return HttpResponse(result)