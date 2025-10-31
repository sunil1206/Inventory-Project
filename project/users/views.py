from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from .models import Account, UserProfile, Subscription
from .forms import RegistrationForm, UserForm, UserProfileForm


# Note: All auth views (login, logout, password reset) are handled by allauth.

def register(request):
    """
    Handles new user registration.
    Account is created as active and given a default 'free' subscription.
    """
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            username = form.cleaned_data['username']

            # create_user now sets is_active=True by default (in models.py)
            Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,
                password=password
            )

            # The post_save signal in models.py handles creation of UserProfile
            # and the default 'free' Subscription.

            messages.success(request, 'Account created successfully. You can now log in.')
            return redirect('account_login')  # Redirect to allauth's login page
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegistrationForm()

    context = {
        'form': form,
    }
    return render(request, 'users/signup.html', context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from .forms import UserForm, UserProfileForm
from .models import Account, UserProfile
from Inventory.models import Supermarket  # ✅ IMPORT THE SUPERMARKET MODEL


# --- Other views like register, login, logout, etc. ---
# ...
# ...

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from .forms import UserForm, UserProfileForm
from .models import Account, UserProfile
from Inventory.models import Supermarket  # ✅ IMPORT THE SUPERMARKET MODEL


# ... (other views like register, login, logout, etc.) ...

@login_required(login_url='account_login')
def dashboard(request):
    """
    Handles both displaying the dashboard with a list of supermarkets
    and processing the form to create a new supermarket.
    """

    # ✅ --- FIX: ADD THIS NEW LOGIC ---
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')

        if not name:
            messages.error(request, 'Supermarket name is required.')
        else:
            # Create the new supermarket and assign the current user as the owner
            Supermarket.objects.create(
                owner=request.user,
                name=name,
                location=location
            )
            messages.success(request, f"Supermarket '{name}' created successfully!")
            # Redirect back to the same page to show the new supermarket in the list
            return redirect('users:dashboard')
            # ✅ --- END OF FIX ---

    # This GET logic runs when the page is first loaded
    supermarkets = Supermarket.objects.filter(owner=request.user)
    context = {
        'supermarkets': supermarkets
    }
    return render(request, 'users/dashboard.html', context)


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserForm, UserProfileForm
from .models import Account, UserProfile  # Make sure to import models


@login_required(login_url='account_login')  # Or your login URL
def profile_edit_view(request):
    """
    Handles viewing and editing the user's profile,
    which consists of the Account and UserProfile models.
    """

    # Your signals should have already created the profile,
    # but we use get_or_create just in case.
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        # Populate the forms with POST data
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=profile)

        # Check if both forms are valid
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()

            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('profile_edit')  # Redirect back to the same page
        else:
            messages.error(request, 'Please correct the errors below.')

    else:
        # Populate forms with existing data (GET request)
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'user': request.user  # Pass the user object for profile picture URL
    }
    return render(request, 'users/dashboard.html', context)


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from .models import Subscription

@login_required
def subscription_renew_view(request):
    # This page shows subscription options and the "Pay Now" button
    # (e.g., your Stripe checkout element)
    context = {
        'subscription': request.user.subscription
    }
    return render(request, 'users/subscription_renew.html', context)

@login_required
def payment_success_view(request):
    # --- This is a DEMO view ---
    # In a real app, a Stripe Webhook would call this view
    # to confirm payment and update the subscription.

    subscription = request.user.subscription

    # Update their plan
    subscription.plan = Subscription.PLAN_PRO
    subscription.start_date = timezone.now()

    # Set their new end date (e.g., 30 days from now)
    subscription.end_date = timezone.now() + timedelta(days=30)

    subscription.is_active = True
    subscription.save()

    messages.success(request, "Thank you! Your Pro plan is now active.")
    return redirect('dashboard') # Redirect to a "pro" feature page