# from django.urls import path
# from .views import ai_expiry_recommendations
#
# app_name = "expiry_ai"
#
# urlpatterns = [
#     path(
#         "supermarket/<int:supermarket_id>/recommendations/",
#         ai_expiry_recommendations,
#         name="recommendations",
#     ),
# ]

from django.urls import path
from .views import expired_products, ai_expiry_recommendations

app_name = "expiry"

urlpatterns = [
    path(
        "supermarket/<int:supermarket_id>/expired/",
        expired_products,
        name="expired_products",
    ),
    path(
        "supermarket/<int:supermarket_id>/recommendations/",
        ai_expiry_recommendations,
        name="recommendations",
    ),
]
