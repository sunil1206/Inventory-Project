from django import forms
from .models import Account, UserProfile
from django.core.exceptions import ValidationError


class RegistrationForm(forms.ModelForm):
    """
    Form for registering a new user. Includes password confirmation.
    """
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter Password',
            'class': 'form-control',
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm Password',
            'class': 'form-control',
        })
    )

    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def __init__(self, *args, **kwargs):
        """
        Apply 'form-control' class and placeholders to all fields.
        """
        super(RegistrationForm, self).__init__(*args, **kwargs)

        self.fields['first_name'].widget.attrs['placeholder'] = 'First Name'
        self.fields['last_name'].widget.attrs['placeholder'] = 'Last Name'
        self.fields['username'].widget.attrs['placeholder'] = 'Username'
        self.fields['email'].widget.attrs['placeholder'] = 'Email Address'

        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'

    def clean_username(self):
        """
        Validate that the username is unique (case-insensitive).
        """
        username = self.cleaned_data.get('username')
        if Account.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken. Please choose a different one.")
        return username

    def clean_email(self):
        """
        Validate that the email is unique (case-insensitive).
        """
        email = self.cleaned_data.get('email')
        if Account.objects.filter(email__iexact=email).exists():
            raise ValidationError("This email address is already registered.")
        return email

    def clean(self):
        """
        Validate that the two password fields match.
        """
        cleaned_data = super(RegistrationForm, self).clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and (password != confirm_password):
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


class UserForm(forms.ModelForm):
    """
    A form for updating the user's basic information (from the Account model).
    """

    class Meta:
        model = Account
        fields = ['first_name', 'last_name', 'phone_number']

    def __init__(self, *args, **kwargs):
        """
        Apply 'form-control' class to all fields.
        """
        super(UserForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class UserProfileForm(forms.ModelForm):
    """
    A form for updating the user's profile details.
    """
    delete_profile_picture = forms.BooleanField(
        required=False,
        label='Delete profile picture',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = UserProfile
        fields = [
            'bio', 'profile_picture', 'address_line_1', 'address_line_2',
            'city', 'state', 'country', 'delete_profile_picture'
        ]

    def __init__(self, *args, **kwargs):
        """
        Apply 'form-control' class to fields.
        """
        super(UserProfileForm, self).__init__(*args, **kwargs)
        self.fields['profile_picture'].widget.attrs['class'] = 'form-control-file'
        self.fields['bio'].widget.attrs['rows'] = 3

        for field_name in self.fields:
            if field_name not in ['profile_picture', 'delete_profile_picture']:
                self.fields[field_name].widget.attrs['class'] = 'form-control'

    def save(self, commit=True):
        """
        Override save to handle the 'delete_profile_picture' checkbox.
        """
        instance = super().save(commit=False)

        if self.cleaned_data.get('delete_profile_picture'):
            if instance.profile_picture:
                instance.delete_profile_picture()  # Call model method

        if commit:
            instance.save()

        return instance