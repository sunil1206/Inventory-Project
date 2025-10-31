# Django core imports
from django.shortcuts import render, redirect, get_object_or_404
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth import get_user_model

# Local app imports
from .models import Account, UserProfile
from .forms import RegistrationForm, UserForm, UserProfileForm

# Get the custom user model
User = get_user_model()


def register(request):
    """
    Handles new user registration using username.
    """
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            username = form.cleaned_data['username']  # Get username from form

            user = Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                email=email,
                username=username,  # Pass username to create_user
                password=password
            )

            # Set user to inactive until activated
            user.is_active = False
            user.save()

            # Send activation email
            current_site = get_current_site(request)
            mail_subject = 'Please activate your account'
            message = render_to_string('users/account_verification_email.html', {
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            messages.success(request, 'Registration successful. Please check your email to verify your account.')
            return redirect('login')
        else:
            # Form is invalid, re-render with errors
            messages.error(request, 'Please correct the errors below.')
    else:
        form = RegistrationForm()

    context = {
        'form': form,
    }
    return render(request, 'users/signup.html', context)


def login(request):
    """
    Handles user login using username.
    """
    if request.method == 'POST':
        username = request.POST['username']  # Changed from 'email'
        password = request.POST['password']

        # Authenticate using username
        user = auth.authenticate(request, username=username, password=password)

        if user is not None:
            auth.login(request, user)
            messages.success(request, 'You are now logged in.')
            return redirect('dashboard')
        else:
            messages.error(request, "Invalid username or password.")
            return redirect('login')

    return render(request, 'users/login.html')


@login_required(login_url='login')
def logout(request):
    """Logs the current user out."""
    auth.logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('login')


def activate(request, uidb64, token):
    """
    Activates a user's account from the link sent via email.
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, "Congratulations! Your account is now activated.")
        return redirect('login')
    else:
        messages.error(request, "Invalid activation link.")
        return redirect('register')


def forgotpassword(request):
    """
    Handles the 'forgot password' request (still uses email).
    """
    if request.method == 'POST':
        email = request.POST['email']

        if User.objects.filter(email=email).exists():
            user = User.objects.get(email__exact=email)

            # Send reset password email
            current_site = get_current_site(request)
            mail_subject = 'Reset your password'
            message = render_to_string('users/reset_password_email.html', {
                'user': user,
                'domain': current_site,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': default_token_generator.make_token(user),
            })
            to_email = email
            send_email = EmailMessage(mail_subject, message, to=[to_email])
            send_email.send()

            messages.success(request, 'Password reset email has been sent to your email address.')
            return redirect('login')
        else:
            messages.error(request, 'No account found with that email address.')
            return redirect('forgotpassword')

    return render(request, 'users/forgotpassword.html')


def resetpassword_validate(request, uidb64, token):
    """
    Validates the password reset link.
    """
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User._default_manager.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        request.session['uid'] = uid
        messages.success(request, 'Please reset your password.')
        return redirect('resetpassword')
    else:
        messages.error(request, 'This link has expired or is invalid.')
        return redirect('login')


def resetpassword(request):
    """
    Renders the new password form and processes it.
    """
    if 'uid' not in request.session:
        messages.error(request, 'Session expired or link is invalid. Please try again.')
        return redirect('forgotpassword')

    if request.method == 'POST':
        password = request.POST['password']
        confirm_password = request.POST['confirm_password']

        if password == confirm_password:
            uid = request.session.get('uid')
            if not uid:
                messages.error(request, 'Session expired. Please try again.')
                return redirect('forgotpassword')

            try:
                user = User.objects.get(pk=uid)
                user.set_password(password)
                user.save()
                del request.session['uid']
                messages.success(request, 'Password reset successful.')
                return redirect('login')
            except User.DoesNotExist:
                messages.error(request, 'User not found. Please try again.')
                return redirect('forgotpassword')
        else:
            messages.error(request, 'Passwords do not match.')

    return render(request, 'users/resetpassword.html')


@login_required(login_url='login')
def dashboard(request):
    """
    Displays the user's main dashboard after login.
    """
    context = {}
    return render(request, 'users/dashboard.html', context)


@login_required(login_url='login')
def edit_profile(request):
    """
    Allows a logged-in user to edit their profile information.
    """
    userprofile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()

            # Form's save method now handles this, but explicit check is fine
            profile_form.save()

            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('edit_profile')
        else:
            messages.error(request, 'Please correct the errors below.')

    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=userprofile)

    context = {
        'profile_form': profile_form,
        'user_form': user_form,
        'userprofile': userprofile,
    }
    return render(request, 'users/edit_profile.html', context)