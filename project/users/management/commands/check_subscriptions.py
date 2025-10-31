from django.core.management.base import BaseCommand
from users.models import Subscription
from django.utils import timezone
import datetime

class Command(BaseCommand):
    help = 'Checks for expired Pro subscriptions and sets them to inactive.'

    def handle(self, *args, **kwargs):
        now = timezone.now()

        # Find all Pro subscriptions that are still marked as active
        # but their end_date is in the past.
        expired_subs = Subscription.objects.filter(
            plan=Subscription.PLAN_PRO,
            is_active=True,
            end_date__lt=now  # The end_date is before now
        )

        # Deactivate them
        count = expired_subs.update(is_active=False)

        if count > 0:
            self.stdout.write(self.style.SUCCESS(f'Successfully deactivated {count} expired subscriptions.'))
        else:
            self.stdout.write(self.style.SUCCESS('No expired subscriptions found.'))