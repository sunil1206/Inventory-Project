from django.core.management.base import BaseCommand
from competitor.models import Competitor

class Command(BaseCommand):
    help = 'Initialize default French competitor configurations'

    def handle(self, *args, **kwargs):
        competitors = [
            {
                "name": "Franprix",
                "search_url_template": "https://www.franprix.fr/rechercher?q={barcode}",
                "price_selector": ".product-price__amount"  # Example selector
            },
            {
                "name": "Carrefour",
                "search_url_template": "https://www.carrefour.fr/s?q={barcode}",
                "price_selector": ".product-card-price__price"
            },
            {
                "name": "E.Leclerc",
                "search_url_template": "https://www.e.leclerc/recherche?q={barcode}",
                "price_selector": ".price--current"
            },
            {
                "name": "Intermarché",
                "search_url_template": "https://www.intermarche.com/recherche/{barcode}",
                "price_selector": ".product-price"
            },
            {
                "name": "Monoprix",
                "search_url_template": "https://www.monoprix.fr/recherche/{barcode}",
                "price_selector": ".grocery-item__price"
            },
            {
                "name": "Auchan",
                "search_url_template": "https://www.auchan.fr/recherche?text={barcode}",
                "price_selector": ".product-price__value"
            },
             {
                "name": "G20",
                "search_url_template": "https://www.supermarchesg20.com/recherche?q={barcode}",
                "price_selector": ".price_container"
            }
        ]

        for comp_data in competitors:
            obj, created = Competitor.objects.update_or_create(
                name=comp_data['name'],
                defaults={
                    'search_url_template': comp_data['search_url_template'],
                    'price_selector': comp_data['price_selector'],
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created competitor: {obj.name}'))
            else:
                self.stdout.write(self.style.WARNING(f'Updated competitor: {obj.name}'))