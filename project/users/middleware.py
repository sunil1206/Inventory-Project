from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from .models import Subscription

class SubscriptionCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the user is authenticated, not staff, and not already on a "safe" page
        if request.user.is_authenticated and not request.user.is_staff:

            # Define pages that an expired user can still access
            safe_paths = [
                reverse('users:subscription_renew'),  # <-- THE FIX
                reverse('account_logout'),      # The logout URL
                # Add any other "safe" URLs, like a contact page
            ]

            # Prevent redirect loops
            if request.path in safe_paths:
                return self.get_response(request)

            # Get the subscription. The @property 'is_valid' does all the work
            try:
                if not request.user.subscription.is_valid:
                    messages.warning(request, "Your plan has expired. Please renew your subscription to continue.")
                    # This redirect was already correct
                    return redirect('users:subscription_renew')
            except Subscription.DoesNotExist:
                # This shouldn't happen because of your signal, but it's safe to handle
                Subscription.objects.create(user=request.user)
                messages.info(request, "Welcome! Your free plan has been set up.")

        # Continue to the requested view
        response = self.get_response(request)
        return response