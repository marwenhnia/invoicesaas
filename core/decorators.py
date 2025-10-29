from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import redirect
from django.contrib import messages

def admin_required(view_func):
    """
    Décorateur qui vérifie que l'utilisateur est staff/superuser.
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
                # Non connecté → login
                messages.warning(request, "Vous devez être connecté en tant qu'administrateur pour accéder à cette page.")
                return redirect(f'/login/?next={request.path}')
            else:
                # Connecté mais pas admin → dashboard user
                messages.error(request, "❌ Accès refusé. Cette page est réservée aux administrateurs.")
                return redirect('core:dashboard')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper