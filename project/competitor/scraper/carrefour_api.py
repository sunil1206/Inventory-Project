import requests
from decimal import Decimal

CARREFOUR_API = (
    "https://www.carrefour.fr/api/v2/search?"
    "query={barcode}&page=1"
)

def scrape_carrefour(product):
    url = CARREFOUR_API.format(barcode=product.barcode)
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()

    items = data.get("entities", [])
    if not items:
        return None

    p = items[0]

    return {
        "name": p.get("name"),
        "barcode": p.get("gtin"),
        "price": Decimal(str(p["price"]["value"])),
        "url": "https://www.carrefour.fr" + p.get("url", "")
    }
