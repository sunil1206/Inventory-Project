from django.contrib import admin

# Register your models here.
from seo.models import SEOSettings


@admin.register(SEOSettings)
class SEOSettingsAdmin(admin.ModelAdmin):
    list_display = ('title',)
    search_fields = ('title',)