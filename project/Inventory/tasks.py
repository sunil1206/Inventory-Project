from celery import shared_task
from .models import Product, CompetitorPrice
from .scraping_utils import scrape_competitor_prices


@shared_task
def scrape_product_task(product_barcode):
    """
    A background Celery task that scrapes competitor prices for a given product.

    This function is NOT called directly by the user's web browser. Instead, a view
    triggers this task, and a separate Celery worker process runs it in the background.

    Args:
        product_barcode (str): The barcode of the product to be scraped.
    """
    try:
        # 1. Find the product in our database using the barcode.
        product = Product.objects.get(pk=product_barcode)

        # 2. Clear out any old pricing data to ensure the results are fresh.
        CompetitorPrice.objects.filter(product=product).delete()

        # 3. Call the main scraping function from scraping_utils.py.
        #    This is the slow part that can take several seconds.
        scraped_data = scrape_competitor_prices(product.barcode, product.name)

        # 4. Loop through the results and save each new price to the database.
        for data in scraped_data:
            CompetitorPrice.objects.create(
                product=product,
                competitor_name=data['competitor_name'],
                price=data['price'],
                # The 'url' field might not be present in all results from the scraper
                url=data.get('url', '')
            )

        # This message will be logged by the Celery worker.
        return f"Successfully scraped {len(scraped_data)} prices for {product.name}."

    except Product.DoesNotExist:
        return f"Error: Product with barcode {product_barcode} not found."
    except Exception as e:
        return f"An unexpected error occurred during scraping for {product_barcode}: {e}"

