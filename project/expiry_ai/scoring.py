# expiry_ai/scoring.py
import math
import re
import unicodedata
from datetime import date
from django.utils import timezone


def normalize_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def confidence_from_support(support_sum: float, alpha: float = 0.8) -> float:
    # confidence = 1 - exp(-alpha * support_sum)
    if support_sum <= 0:
        return 0.0
    return 1.0 - math.exp(-alpha * support_sum)


def time_risk(expiry_date: date, horizon_days: int = 14) -> float:
    """
    1.0 if expired, else linear ramp when within horizon.
    """
    today = timezone.localdate()
    d = (expiry_date - today).days
    if d <= 0:
        return 1.0
    if d >= horizon_days:
        return 0.0
    return (horizon_days - d) / float(horizon_days)


def risk(confidence: float, expiry_date: date, horizon_days: int = 14) -> float:
    return float(confidence) * float(time_risk(expiry_date, horizon_days=horizon_days))


def level_from_confidence(conf: float) -> str:
    if conf >= 0.85:
        return "confirmed"
    if conf >= 0.65:
        return "likely"
    return "weak"
