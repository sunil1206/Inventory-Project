
from django import forms
from .models import Promotion, PricingRule
from Inventory.models import Product, Category

class PricingRuleForm(forms.ModelForm):
    class Meta:
        model = PricingRule
        fields = ['name', 'rule_type', 'amount', 'category', 'supplier', 'days_until_expiry', 'priority']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'rule_type': forms.Select(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'amount': forms.NumberInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'category': forms.Select(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'supplier': forms.Select(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'days_until_expiry': forms.NumberInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'priority': forms.NumberInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
        }

class PromotionForm(forms.ModelForm):
    # These querysets ensure the forms only show relevant choices
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Promotion
        fields = ['name', 'start_date', 'end_date', 'discount_type', 'discount_value', 'products', 'categories', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'discount_type': forms.Select(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'discount_value': forms.NumberInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
        }
