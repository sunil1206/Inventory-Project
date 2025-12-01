# competitor/urls.py

from django.urls import path
from . import views

app_name = 'competitor'

urlpatterns = [
    path('compare/<int:supermarket_id>/', views.competitor_compare_all, name='competitor_compare'),
    path('refresh/<str:product_id>/', views.refresh_price, name='refresh'),
    path('trend-data/', views.price_trend_data, name='trend_data'),
]
