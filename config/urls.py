"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from core import views
from core.views import CustomLoginView
from core import views as core_views
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Pages publiques
    path('', views.landing_page, name='landing'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # App
    path('app/', include('core.urls')),
    path('stripe/webhook/', core_views.stripe_webhook, name='stripe_webhook'),
    path('mentions-legales/', TemplateView.as_view(template_name='legal/mentions.html'), name='mentions'),
    path('cgv/', TemplateView.as_view(template_name='legal/cgv.html'), name='cgv'),
    path('robots.txt', core_views.robots_txt, name='robots'),
    path('sitemap.xml', core_views.sitemap_xml, name='sitemap'),
]
