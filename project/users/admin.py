from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, UserProfile, Subscription

class UserProfileInline(admin.StackedInline):
    """
    Makes UserProfile editable from the Account admin page.
    """
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'

class SubscriptionInline(admin.StackedInline):
    """
    Makes Subscription editable from the Account admin page.
    """
    model = Subscription
    can_delete = False
    verbose_name_plural = 'Subscription'
    fk_name = 'user'

class AccountAdmin(UserAdmin):
    """
    Customizes the display of the Account model in the admin.
    """
    list_display = ('username', 'email', 'first_name', 'last_name', 'last_login', 'date_joined', 'is_active')
    list_display_links = ('username', 'email')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)

    # Add the inlines
    inlines = (UserProfileInline, SubscriptionInline)

    # Required for custom user models
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()

# Unregister the default Group model if you don't use it
# from django.contrib.auth.models import Group
# admin.site.unregister(Group)

admin.site.register(Account, AccountAdmin)

# We don't need to register UserProfile or Subscription separately
# as they are now 'inlined' in the Account admin.
# admin.site.register(UserProfile)
# admin.site.register(Subscription)