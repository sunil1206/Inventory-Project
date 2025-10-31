from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, UserProfile

class AccountAdmin(UserAdmin):
    """
    Customize the display of the Account model in the admin.
    """
    list_display = ('username', 'email', 'first_name', 'last_name', 'last_login', 'date_joined', 'is_active')
    list_display_links = ('username', 'email')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('-date_joined',)

    # Required for custom user models
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()

class UserProfileAdmin(admin.ModelAdmin):
    """
    Customize the display of the UserProfile model in the admin.
    """
    list_display = ('user', 'city', 'state', 'country')
    list_display_links = ('user',)

# Register your models
admin.site.register(Account, AccountAdmin)
admin.site.register(UserProfile, UserProfileAdmin)