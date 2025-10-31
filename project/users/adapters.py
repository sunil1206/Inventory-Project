from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import get_adapter
from allauth.exceptions import ImmediateHttpResponse
from allauth.account.models import EmailAddress
from django.contrib import messages
from django.shortcuts import redirect


class MySocialAccountAdapter(DefaultSocialAccountAdapter):

    def save_user(self, request, sociallogin, form=None):
        """
        Saves a new social user.
        This is where we auto-generate a unique username.
        """
        user = sociallogin.user

        if not user.username:
            email = user.email
            if email:
                base_username = email.split('@')[0]
                # This will find a unique username by adding a number if needed
                # e.g., 'john', 'john2', 'john3'
                user.username = get_adapter().generate_unique_username([
                    base_username,
                    user.first_name,
                    user.last_name,
                    'user'
                ])
            else:
                # Fallback if no email is provided
                user.username = get_adapter().generate_unique_username(['user'])

        # Save the user
        user.save()
        return super().save_user(request, sociallogin, form)

    def pre_social_login(self, request, sociallogin):
        """
        This links an existing user (by email) to their social account.
        """
        # Check if the user's email is verified by Google
        if sociallogin.account.provider == 'google' and \
                sociallogin.account.extra_data.get('email_verified'):

            email = sociallogin.user.email
            if email:
                try:
                    # Find user by email
                    user = self.get_user_model().objects.get(email__iexact=email)

                    # Set the user to active (if they weren't already)
                    # This is safe because Google has verified their email.
                    if not user.is_active:
                        user.is_active = True
                        user.save()

                    # Set the email as verified in allauth
                    EmailAddress.objects.get_or_create(user=user, email=email,
                                                       defaults={'verified': True, 'primary': True})

                    # Connect the social account to the existing user
                    sociallogin.connect(request, user)

                    # Stop the allauth flow and log the user in
                    messages.success(request, f"Welcome back, {user.username}!")
                    raise ImmediateHttpResponse(redirect('dashboard'))

                except self.get_user_model().DoesNotExist:
                    # User doesn't exist, so they will proceed to the signup flow
                    pass