# # from celery import shared_task
# # from django.utils import timezone
# # from Inventory.models import Product, ProductPrice, Supermarket
# # from competitor.scraper import scrape_product_by_barcode
# #
# # @shared_task
# # def scrape_product_competitors_task(product_id: str):
# #     """
# #     Scrape all active competitors for a single product (by barcode PK).
# #     """
# #     from Inventory.models import Product
# #     try:
# #         product = Product.objects.get(pk=product_id)
# #     except Product.DoesNotExist:
# #         return f"Product {product_id} not found"
# #
# #     return scrape_product_by_barcode(product)
# #
# #
# # @shared_task
# # def scrape_supermarket_products_task(supermarket_id: int):
# #     """
# #     Scrape all products that have a price in a given supermarket.
# #     Good for manual or scheduled runs.
# #     """
# #     from Inventory.models import Supermarket, ProductPrice
# #     try:
# #         supermarket = Supermarket.objects.get(pk=supermarket_id)
# #     except Supermarket.DoesNotExist:
# #         return f"Supermarket {supermarket_id} not found"
# #
# #     price_rows = ProductPrice.objects.filter(supermarket=supermarket).select_related("product")
# #
# #     count = 0
# #     for row in price_rows:
# #         if row.product:
# #             scrape_product_by_barcode(row.product)
# #             count += 1
# #     return f"Scraped {count} products for supermarket {supermarket.name}"
# #
# #
# # @shared_task
# # def scrape_all_products_nightly():
# #     """
# #     Nightly job: scrape all products that belong to any supermarket price list.
# #     Triggers every day at 05:00 via Celery Beat.
# #     """
# #     from Inventory.models import ProductPrice
# #     seen = set()
# #     count = 0
# #
# #     for row in ProductPrice.objects.select_related("product"):
# #         if row.product and row.product.barcode not in seen:
# #             scrape_product_by_barcode(row.product)
# #             seen.add(row.product.barcode)
# #             count += 1
# #
# #     return f"Nightly scrape finished at {timezone.now()}, products scraped: {count}"
#
#
# # competitor/tasks.py
# from celery import shared_task
# from Inventory.models import Product
# from competitor.models import Competitor
# from competitor.scraper import scrape_selenium
#
# @shared_task
# def scrape_product_competitors_task(product_id):
#     product = Product.objects.get(pk=product_id)
#     competitors = Competitor.objects.filter(is_active=True)
#     return scrape_selenium(product, competitors)

# competitor/tasks.py

from celery import shared_task
from Inventory.models import Product
from competitor.models import Competitor
from competitor.scraper.scraper import scrape_all_competitors

@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def scrape_product_competitors_task(self, product_id):
    product = Product.objects.get(pk=product_id)
    competitors = Competitor.objects.filter(is_active=True)
    return scrape_all_competitors(product, competitors)
