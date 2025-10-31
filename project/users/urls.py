from django.urls import path
from . import views

app_name = 'users'
urlpatterns = [
    # Your custom registration
    path('register/', views.register, name='register'),

    # Your custom account pages
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/edit/', views.profile_edit_view, name='profile_edit'),
 path('renew-subscription/', views.subscription_renew_view, name='subscription_renew'),
    path('payment-success/', views.payment_success_view, name='payment_success'), # Example


    # All other auth URLs (login, logout, password_reset, google_login)
    # are handled by `allauth` in your main project's urls.py
]