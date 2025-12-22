import requests
from decimal import Decimal

LECLERC_API = (
    "https://api.e-leclerc.com/catalog/v1/products?"
    "search={barcode}&size=1"
)

def scrape_leclerc(product):
    r = requests.get(
        LECLERC_API.format(barcode=product.barcode),
        timeout=15,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    r.raise_for_status()
    data = r.json()

    hits = data.get("items", [])
    if not hits:
        return None

    p = hits[0]

    return {
        "name": p["designation"],
        "barcode": p["ean"],
        "price": Decimal(str(p["price"]["amount"])),
        "url": p.get("url")
    }
