from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from Inventory.models import Supermarket  # Import the Supermarket model from your inventory app


@login_required(login_url='/accounts/login/')
def dashboard_view(request):
    """
    Displays the user's dashboard, which lists their supermarkets and allows
    them to create new ones.
    """
    # Handle the creation of a new supermarket
    if request.method == 'POST':
        name = request.POST.get('name')
        location = request.POST.get('location')
        if name:  # Basic validation
            Supermarket.objects.create(owner=request.user, name=name, location=location)
        return redirect('users:dashboard')

    # Get the list of supermarkets owned by the current user
    supermarkets = Supermarket.objects.filter(owner=request.user).order_by('name')

    context = {
        'user': request.user,
        'supermarkets': supermarkets
    }
    return render(request, 'users/dashboard.html', context)

