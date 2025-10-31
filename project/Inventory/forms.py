from django import forms
from .models import Rack, Category


class RackForm(forms.ModelForm):
    class Meta:
        model = Rack
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'placeholder': 'e.g., Aisle 5',
                'required': True,
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500',
                'rows': 2,
                'placeholder': 'e.g., Frozen Goods Section'
            }),
        }

from django import forms
from .models import Product # Make sure to import your Product model

# class ProductForm(forms.ModelForm):
#     class Meta:
#         model = Product
#         # List all fields that are in your template's form
#         fields = [
#             'barcode', 'name', 'brand', 'category',
#             'cover_image', 'image_url', 'suppliers', 'description'
#         ]
#
#
# class CategoryForm(forms.ModelForm):
#     """
#     Form for creating and editing a Category.
#     """
#     class Meta:
#         model = Category
#         fields = ['name', 'description']
#         widgets = {
#             'name': forms.TextInput(attrs={
#                 'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm',
#                 'placeholder': 'e.g., Dairy, Produce, Bakery'
#             }),
#             'description': forms.Textarea(attrs={
#                 'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm',
#                 'rows': 3,
#                 'placeholder': 'Optional description for this category.'
#             }),
#         }


from django import forms
from .models import Category, Product
from .models import Supplier


class CategoryForm(forms.ModelForm):
    """
    Form for creating and editing a Category.
    """

    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'description': forms.Textarea(
                attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm', 'rows': 3}),
        }


class ProductForm(forms.ModelForm):
    """
    Form for creating and editing a Product.
    """
    # This field is used by the edit_product_view to handle image deletion
    clear_cover_image = forms.BooleanField(required=False, widget=forms.CheckboxInput,
                                           label="Clear current uploaded image")

    # We can override the suppliers field to use a better widget
    suppliers = forms.ModelMultipleChoiceField(
        queryset=Supplier.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'w-full h-32 p-2 border border-gray-300 rounded-md shadow-sm'}),
        required=False
    )

    class Meta:
        model = Product
        fields = [
            'barcode', 'name', 'brand', 'category',
            'cover_image', 'image_url', 'suppliers', 'description'
        ]

        # This makes the form look good with Tailwind CSS
        widgets = {
            'barcode': forms.TextInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'name': forms.TextInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'brand': forms.TextInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'category': forms.Select(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm'}),
            'cover_image': forms.FileInput(attrs={
                'class': 'w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100'}),
            'image_url': forms.URLInput(attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm',
                                               'placeholder': 'https://example.com/image.jpg'}),
            'description': forms.Textarea(
                attrs={'class': 'mt-1 w-full p-2 border border-gray-300 rounded-md shadow-sm', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        # Make barcode read-only if we are editing (instance is passed)
        if self.instance and self.instance.pk:
            self.fields['barcode'].widget.attrs['readonly'] = True
            self.fields['barcode'].widget.attrs['class'] += ' bg-gray-100 cursor-not-allowed'

