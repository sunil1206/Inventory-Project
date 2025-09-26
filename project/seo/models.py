from django.db import models

# Create your models here.

# Create your models here.
class SEOSettings(models.Model):
    PAGE_CHOICES = (
        ('Home', 'Home'),
        ('About Us', 'About Us'),
        ('Service', 'Service'),
        ('Contact', 'Contact'),
        # Add more choices as needed
    )
    title = models.CharField(max_length=100, choices=PAGE_CHOICES)
    meta_keywords = models.CharField(max_length=255)
    meta_description = models.TextField()

    def __str__(self):
        return f"{self.title} SEO Settings"