# myapp/sitemaps.py

from django.contrib import sitemaps
from django.urls import reverse

class StaticViewSitemap(sitemaps.Sitemap):
    priority = 0.5
    changefreq = 'daily'

    def items(self):
        return ['index', 'about', 'contact','service']  # Add the names of your views here

    def location(self, item):
        return reverse(item)

from django.views.decorators.http import require_GET
from django.http import HttpResponse

@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Allow: /",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")
