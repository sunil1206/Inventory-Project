from difflib import SequenceMatcher

def name_similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def compute_confidence(product, scraped):
    score = 0.0

    if scraped.get("barcode") == product.barcode:
        score += 0.7

    if scraped.get("name"):
        sim = name_similarity(product.name, scraped["name"])
        score += min(sim * 0.2, 0.2)

    if scraped.get("price"):
        score += 0.1

    return round(min(score, 1.0), 2)
