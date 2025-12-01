# import requests
# from bs4 import BeautifulSoup
# from decimal import Decimal
# import re
# from django.utils import timezone
# from .models import Competitor, CompetitorPriceSnapshot
# from Inventory.api_clients import call_scraper_api  # Re-using your existing API client
#
#
# def clean_price(price_str):
#     """
#     Extracts a decimal price from strings like "3,50 €", "€ 3.50", "3.50".
#     """
#     if not price_str: return None
#     # Remove currency symbols and whitespace
#     clean = price_str.replace('€', '').replace('$', '').strip()
#     # Standardize decimal separator (French comma to dot)
#     clean = clean.replace(',', '.')
#
#     # Regex to find the number
#     match = re.search(r"(\d+\.?\d*)", clean)
#     return Decimal(match.group(1)) if match else None
#
#
# def scrape_product_by_barcode(product):
#     """
#     Iterates through ALL active competitors, searches for the product by barcode,
#     and saves the price snapshot if found.
#     """
#     competitors = Competitor.objects.filter(is_active=True)
#     results_log = []
#
#     for comp in competitors:
#         # 1. Dynamically build the search URL
#         # e.g. https://www.franprix.fr/recherche/3017620422003
#         search_url = comp.search_url_template.replace("{barcode}", product.barcode)
#
#         try:
#             # 2. Fetch HTML using your ScraperAPI client (essential for these sites)
#             html_content = call_scraper_api(search_url)
#
#             if not html_content:
#                 results_log.append(f"{comp.name}: Failed (No content)")
#                 continue
#
#             soup = BeautifulSoup(html_content, 'html.parser')
#
#             # 3. Find the price using the CSS selector stored in the DB
#             price_tag = soup.select_one(comp.price_selector)
#
#             if price_tag:
#                 price = clean_price(price_tag.get_text())
#                 if price:
#                     # 4. Save the Snapshot
#                     CompetitorPriceSnapshot.objects.create(
#                         product=product,
#                         competitor=comp,
#                         price=price,
#                         product_url=search_url  # Saving the search URL as source
#                     )
#                     results_log.append(f"{comp.name}: Found €{price}")
#                 else:
#                     results_log.append(f"{comp.name}: Price parse error")
#             else:
#                 results_log.append(f"{comp.name}: Product not found or selector changed")
#
#         except Exception as e:
#             results_log.append(f"{comp.name}: Error {str(e)}")
#
#     return results_log


import time
from decimal import Decimal
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

from competitor.models import CompetitorPriceSnapshot


def clean_price(text):
    if not text: return None
    text = text.replace("€", "").replace(",", ".").strip()
    for part in text.split():
        try:
            return Decimal(part)
        except:
            pass
    return None


def new_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--no-sandbox")
    options.add_argument(
        "user-agent=Mozilla/5.0 Chrome/123 Safari/537.36"
    )

    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )


def scrape_selenium(product, competitors):
    driver = new_driver()
    logs = []

    for comp in competitors:
        url = comp.search_url_template.replace("{barcode}", product.barcode)

        try:
            driver.get(url)
            time.sleep(5)

            el = driver.find_element(By.CSS_SELECTOR, comp.price_selector)
            price = clean_price(el.text)

            if price:
                CompetitorPriceSnapshot.objects.create(
                    product=product,
                    competitor=comp,
                    price=price,
                    scraped_at=timezone.now(),
                    product_url=url,
                )
                logs.append(f"{comp.name}: €{price}")
            else:
                logs.append(f"{comp.name}: PRICE NOT FOUND")

        except Exception as e:
            logs.append(f"{comp.name}: ERROR {e}")

    driver.quit()
    return logs

