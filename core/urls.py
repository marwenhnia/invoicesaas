from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    # Invoices
    path('invoice/create/', views.invoice_create, name='invoice_create'),
    path('invoice/<int:invoice_id>/', views.invoice_detail, name='invoice_detail'),
    path('invoice/<int:invoice_id>/edit/', views.invoice_edit, name='invoice_edit'),
    path('invoice/<int:invoice_id>/pdf/', views.generate_invoice_pdf, name='invoice_pdf'),
    path('invoice/<int:invoice_id>/mark-paid/', views.invoice_mark_paid, name='invoice_mark_paid'),
    path('invoice/<int:invoice_id>/mark-sent/', views.invoice_mark_sent, name='invoice_mark_sent'),
    path('invoice/<int:invoice_id>/send-email/', views.invoice_send_email, name='invoice_send_email'),
    path('invoice/<int:invoice_id>/delete/', views.invoice_delete, name='invoice_delete'),
    
    # Clients
    path('clients/', views.client_list, name='client_list'),
    path('clients/create/', views.client_create, name='client_create'),
    path('clients/<int:client_id>/', views.client_detail, name='client_detail'),
    path('clients/<int:client_id>/edit/', views.client_edit, name='client_edit'),
    
    # Settings & Upgrade
    path('settings/', views.user_settings, name='settings'),
    path('upgrade/', views.upgrade_to_premium, name='upgrade'),
    path('clients/<int:client_id>/delete/', views.client_delete, name='client_delete'),
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout'),
    path('payment-success/', views.payment_success, name='payment_success'),
    path('cancel-subscription/', views.cancel_subscription, name='cancel_subscription'),
]