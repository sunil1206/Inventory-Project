from django.shortcuts import render

# Create your views here.
from seo.models import SEOSettings

def handling_404(request, exception):
    return render(request, 'core/404.html', {})

def index(request):
    canonical_url = request.build_absolute_uri()
    try:
        seo_settings = SEOSettings.objects.get(title='Home')
    except SEOSettings.DoesNotExist:
        seo_settings = None  # Or provide default SEO settings

    context = {'canonical_url': canonical_url,
               'seo_settings':seo_settings
    }
    return render(request, 'core/index.html',context)


def about(request):
    canonical_url = request.build_absolute_uri()
    try:
        seo_settings = SEOSettings.objects.get(title='About Us')
    except SEOSettings.DoesNotExist:
        seo_settings = None  # Or provide default SEO settings
    context = {'canonical_url': canonical_url,
               'seo_settings': seo_settings
               }
    return render(request, 'core/aboutpage.html',context)

def service(request):
    canonical_url = request.build_absolute_uri()
    try:
        seo_settings = SEOSettings.objects.get(title='Service')
    except SEOSettings.DoesNotExist:
        seo_settings = None  # Or provide default SEO settings
    context = {'canonical_url': canonical_url,
               'seo_settings': seo_settings
               }
    return render(request, 'core/servicepage.html', context)

def contact(request):
    canonical_url = request.build_absolute_uri()
    try:
        seo_settings = SEOSettings.objects.get(title='Contact')
    except SEOSettings.DoesNotExist:
        seo_settings = None  # Or provide default SEO settings
    context = {'canonical_url': canonical_url,
               'seo_settings': seo_settings
               }
    return render(request, 'core/contact.html', context)


