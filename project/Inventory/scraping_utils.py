from bs4 import BeautifulSoup
import re
from decimal import Decimal
from .api_clients import call_scraper_api
import requests


def get_product_info_cascade(barcode):
    """
    Attempts to get product information from a cascade of sources to ensure the best
    possible data enrichment for a wide variety of products.

    Returns:
        dict: A dictionary with product details.
    """
    # 1. Primary Source: Open Food Facts (Best for food items)
    try:
        url = f"https://fr.openfoodfacts.org/api/v0/product/{barcode}.json"
        data = requests.get(url, timeout=10).json()
        if data.get('status') == 1 and data.get('product', {}).get('product_name'):
            prod_data = data['product']
            return {
                'name': prod_data.get('product_name'),
                'quantity': prod_data.get('quantity', None),
                'brand': prod_data.get('brands', ''),
                'nutriscore_grade': prod_data.get('nutriscore_grade', None),
                'image_url': prod_data.get('image_url', ''),
                'description': prod_data.get('generic_name_fr', '')
            }
    except requests.RequestException:
        pass  # Failed, proceed to the next source

    # 2. Secondary Source: Barcode Lookup (Good for non-food items)
    try:
        url_to_scrape = f"https://www.barcodelookup.com/{barcode}"
        html_content = call_scraper_api(url_to_scrape)
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
            # These selectors are specific to barcodelookup.com and are subject to change.
            name_tag = soup.select_one('h4')
            if name_tag:
                return {
                    'name': name_tag.text.strip(),
                    'brand': '',
                    'image_url': '',
                    'description': f'Information sourced from Barcode Lookup for barcode {barcode}.'
                }
    except Exception:
        pass  # Failed, proceed to the final fallback

    # 3. Final Fallback: Create a placeholder name
    return {
        'name': f"Product {barcode}",
        'brand': '',
        'image_url': '',
        'description': ''
    }


def scrape_competitor_prices(barcode, product_name):
    """
    Scrapes multiple, specific competitor websites for the price of a given product.
    This is designed to be run in the background by Celery.
    """
    all_prices = []

    # --- Carrefour Scraper ---
    try:
        url_carrefour = f"https://www.carrefour.fr/s?q={barcode}"
        html_carrefour = call_scraper_api(url_carrefour)
        if html_carrefour:
            soup = BeautifulSoup(html_carrefour, 'html.parser')
            # NOTE: This CSS selector is an example and is highly likely to change.
            # A robust scraper would have multiple fallback selectors.
            price_tag = soup.select_one('.product-card__price span')
            if price_tag:
                price_cleaned = re.sub(r'[^\d,]', '', price_tag.text).replace(',', '.')
                all_prices.append({'competitor_name': 'Carrefour', 'price': Decimal(price_cleaned)})
    except Exception as e:
        print(f"Failed to scrape Carrefour: {e}")

    # --- Monoprix Scraper ---
    try:
        url_monoprix = f"https://www.monoprix.fr/recherche/{barcode}"
        html_monoprix = call_scraper_api(url_monoprix)
        if html_monoprix:
            soup = BeautifulSoup(html_monoprix, 'html.parser')
            # NOTE: This CSS selector is an example.
            price_tag = soup.select_one('.grocery-item__price')
            if price_tag:
                price_cleaned = re.sub(r'[^\d,]', '', price_tag.text).replace(',', '.')
                all_prices.append({'competitor_name': 'Monoprix', 'price': Decimal(price_cleaned)})
    except Exception as e:
        print(f"Failed to scrape Monoprix: {e}")

    # --- E.Leclerc & Franprix ---
    # These sites are often more complex and may require more advanced scraping techniques
    # (e.g., handling store selection modals, rendering heavy JavaScript), which is where
    # the scraping API's `render=true` parameter would be essential.

    return all_prices

# import requests
# from bs4 import BeautifulSoup
# import re
# from decimal import Decimal
# from .api_clients import call_scraper_api
#
#
# def scrape_google_shopping(product_name, location):
#     """
#     Scrapes Google Shopping for competitor prices of a given product near a specific location.
#     This is a simpler and more robust method than scraping individual retail sites.
#
#     Args:
#         product_name (str): The name of the product to search for.
#         location (str): The location of the user's supermarket to narrow down the search.
#
#     Returns:
#         list: A list of dictionaries with competitor pricing data.
#     """
#     if not product_name:
#         return []
#
#     # Prepare a smart search query for Google Shopping, targeting the French market.
#     query = f"{product_name} near {location}"
#     url_to_scrape = f"https://www.google.com/search?q={requests.utils.quote(query)}&tbm=shop&hl=fr&gl=fr"
#
#     # Use the reliable API client to get the webpage HTML
#     html_content = call_scraper_api(url_to_scrape)
#     if not html_content:
#         print("Scraping failed: No HTML content was returned from the API client.")
#         return []
#
#     soup = BeautifulSoup(html_content, 'html.parser')
#
#     competitors = []
#     target_stores = ['carrefour', 'e.leclerc', 'monoprix', 'franprix', 'auchan']
#
#     # This CSS selector targets the main container for each shopping result on Google.
#     # While this can still change, we only have to maintain this one selector.
#     results = soup.select('div.sh-dgr__content')
#
#     for result in results:
#         store_name_tag = result.select_one('div.aULzUe')
#         price_tag = result.select_one('span.HRLxBb')
#         link_tag = result.select_one('a.sh-dgr__offer-content')
#
#         if store_name_tag and price_tag and link_tag:
#             store_name = store_name_tag.text.strip().lower()
#             # Check if the result is from one of our target supermarkets
#             if any(target in store_name for target in target_stores):
#                 price_text = price_tag.text.strip()
#                 product_url = "https://www.google.com" + link_tag['href']
#
#                 # Clean the price string (e.g., "3,50 €" -> "3.50")
#                 price_cleaned = re.sub(r'[^\d,]', '', price_text).replace(',', '.')
#                 try:
#                     price = Decimal(price_cleaned)
#                     competitors.append({
#                         'competitor_name': store_name_tag.text.strip(),
#                         'price': price,
#                         'url': product_url
#                     })
#                 except Exception:
#                     # Could not convert the cleaned price, skip this result
#                     continue
#
#     return competitors
#
#
# def scrape_competitor_prices():
#     return None