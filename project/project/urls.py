"""
URL configuration for project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.contrib.sitemaps.views import sitemap
from seo.sitemaps import StaticViewSitemap, robots_txt

sitemaps = {
    'static': StaticViewSitemap,
}

from project import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('seo/', include('seo.urls')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
path('', include('Inventory.urls')),
path('accounts/', include('allauth.urls')), # Allauth URLs
path('users/', include('users.urls')),
path('pricing/', include('pricing.urls')),
path('product_price/', include('product_price.urls')),
path("packaging/", include("order.urls")),


]

from core.views import handling_404

handler404 = handling_404

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL,
                         document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)