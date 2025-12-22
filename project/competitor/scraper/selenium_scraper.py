from bs4 import BeautifulSoup
from decimal import Decimal
import re
import time
import random

from .selenium_driver import get_driver


def normalize_price(text):
    if not text:
        return None

    text = text.replace(",", ".")
    match = re.search(r"(\d+(\.\d+)?)", text)
    return Decimal(match.group(1)) if match else None


def scrape_selenium(product, competitor):
    """
    Selenium-based fallback scraper
    Used for Franprix, Lidl, Aldi, etc.
    """
    driver = get_driver(headless=True)

    try:
        url = competitor.search_url_template.format(
            barcode=product.barcode
        )
        driver.get(url)
        time.sleep(random.uniform(3, 6))

        soup = BeautifulSoup(driver.page_source, "html.parser")

        price_el = soup.select_one(competitor.price_selector)
        if not price_el:
            return None

        price = normalize_price(price_el.get_text(strip=True))
        if price is None:
            return None

        return {
            "name": product.name,
            "barcode": product.barcode,
            "price": price,
            "url": driver.current_url,
        }

    finally:
        driver.quit()
