import requests
from django.conf import settings


def call_scraper_api(url_to_scrape):
    """
    Calls a third-party scraping service to reliably fetch the HTML of a target URL.

    This function acts as a centralized client for our scraping provider. If we ever
    want to switch from ScraperAPI to another service, this is the only place
    we need to change the code.

    Args:
        url_to_scrape (str): The URL of the page you want to scrape (e.g., a Google Shopping search results page).

    Returns:
        str: The full HTML content of the page as a string, or None if the request fails.
    """
    # 1. Securely get the API key from your project's settings.py file.
    #    This avoids hardcoding sensitive information in your application code.
    api_key = getattr(settings, 'SCRAPER_API_KEY', None)
    if not api_key:
        print("FATAL ERROR: SCRAPER_API_KEY is not defined in your settings.py file.")
        return None

    # 2. Define the payload for the scraping service.
    #    This example is specifically for ScraperAPI. Other services might have
    #    different parameter names.
    payload = {
        'api_key': api_key,
        'url': url_to_scrape,
        'country_code': 'fr'  # Ensure results are specific to the French market
    }

    # 3. Make the request and handle potential errors.
    try:
        # The endpoint for ScraperAPI
        api_endpoint = 'http://api.scraperapi.com'

        response = requests.get(api_endpoint, params=payload, timeout=60)  # 60-second timeout for long requests

        # This will automatically raise an exception for bad status codes (like 401 Unauthorized or 429 Too Many Requests)
        response.raise_for_status()

        # If the request was successful, return the HTML text
        return response.text

    except requests.RequestException as e:
        # This will catch any network errors, timeouts, or bad status codes.
        print(f"Error calling the scraping API: {e}")
        return None

