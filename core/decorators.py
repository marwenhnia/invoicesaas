from django.shortcuts import redirect
from django.contrib import messages
from core.models import UserProfile
from django.utils import timezone
from datetime import timedelta

def admin_required(view_func):
    """
    Décorateur qui vérifie que l'utilisateur est staff/superuser.
    Crée automatiquement un profile si manquant.
    """
    def check_admin(user):
        if not user.is_authenticated:
            return False
        if not (user.is_staff or user.is_superuser):
            return False
        return True
    
    def wrapper(request, *args, **kwargs):
        if not check_admin(request.user):
            if not request.user.is_authenticated:
                messages.warning(request, "Vous devez être connecté en tant qu'administrateur.")
                return redirect(f'/login/?next={request.path}')
            else:
                messages.error(request, "❌ Accès refusé. Réservé aux administrateurs.")
                return redirect('core:dashboard')
        
        # CRITIQUE : Crée le profile si manquant (pour les anciens superusers)
        if not hasattr(request.user, 'profile'):
            UserProfile.objects.create(
                user=request.user,
                is_premium=True,
                trial_end_date=timezone.now() + timedelta(days=9999)
            )
        
        return view_func(request, *args, **kwargs)
    
    return wrapper