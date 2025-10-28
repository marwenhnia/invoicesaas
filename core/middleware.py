from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages


class SubscriptionMiddleware:
    """
    Vérifie que l'utilisateur a un accès valide (essai ou premium).
    Redirige vers la page d'upgrade si l'essai est terminé.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Pages autorisées sans vérification
        allowed_paths = [
            '/login/',
            '/signup/',
            '/logout/',
            '/app/upgrade/',
            '/app/settings/',
            '/admin/',
            '/',  # Landing page
        ]
        
        # Si l'utilisateur est connecté
        if request.user.is_authenticated:
            # Si l'utilisateur est staff/admin, on ne bloque rien
            if request.user.is_staff or request.user.is_superuser:
                return self.get_response(request)
            
            # Vérifie si le profil existe
            if hasattr(request.user, 'profile'):
                # Si l'accès n'est pas autorisé ET que ce n'est pas une page autorisée
                path_allowed = any(request.path.startswith(path) for path in allowed_paths)
                
                if not request.user.profile.can_access_app() and not path_allowed:
                    messages.error(
                        request, 
                        '🔒 Votre période d\'essai est terminée. Abonnez-vous pour continuer à utiliser InvoiceSnap.'
                    )
                    return redirect('core:upgrade')
        
        response = self.get_response(request)
        return response