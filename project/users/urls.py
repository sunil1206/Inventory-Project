from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # This URL pattern maps the 'dashboard/' URL to your dashboard_view
    path('dashboard/', views.dashboard_view, name='dashboard'),
]

