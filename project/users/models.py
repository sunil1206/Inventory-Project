from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db.models.signals import post_save
from django.dispatch import receiver


# --- Custom User Manager ---

class MyAccountManager(BaseUserManager):
    def create_user(self, first_name, last_name, username, email, password=None):
        if not email:
            raise ValueError('User must have an email address')
        if not username:
            raise ValueError('User must have a username')

        user = self.model(
            email=self.normalize_email(email),
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

        user.set_password(password)
        user.is_active = True  # <-- User is now active by default
        user.save(using=self._db)
        return user

    def create_superuser(self, first_name, last_name, email, username, password):
        user = self.create_user(
            email=self.normalize_email(email),
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


# --- Custom User Model ---

class Account(AbstractBaseUser):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=50, blank=True)

    # Required fields
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)  # <-- Changed to True
    is_superuser = models.BooleanField(default=False)

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']

    objects = MyAccountManager()

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return True


# --- User Profile Model ---

class UserProfile(models.Model):
    user = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='userprofile/', blank=True, null=True)
    address_line_1 = models.CharField(max_length=100, blank=True)
    address_line_2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.user.username

    def delete_profile_picture(self):
        if self.profile_picture:
            self.profile_picture.delete(save=True)
            self.profile_picture = None
            self.save()


# --- Subscription Model ---
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone  # Import timezone


# ... (MyAccountManager, Account, UserProfile models) ...

class Subscription(models.Model):
    PLAN_FREE = 'free'
    PLAN_PRO = 'pro'

    PLAN_CHOICES = (
        (PLAN_FREE, 'Free'),
        (PLAN_PRO, 'Pro'),
    )
    # ... (existing fields: PLAN_FREE, PLAN_PRO, etc.) ...
    user = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='subscription')
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_FREE)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True, help_text="Null for free plans, set for pro plans")
    is_active = models.BooleanField(default=True)  # This field is still useful for manual deactivation

    def __str__(self):
        return f"{self.user.username} - {self.get_plan_display()} Plan"

    @property
    def is_valid(self):
        """
        Checks if the subscription is currently active and valid.
        """
        # If it was manually deactivated (e.g., failed payment)
        if not self.is_active:
            return False

        # Free plans are always valid as long as they are active
        if self.plan == self.PLAN_FREE:
            return True

        # Pro plans must have an end date and it must be in the future
        if self.plan == self.PLAN_PRO:
            if self.end_date is None:
                return False  # Pro plan with no end date is invalid
            return timezone.now() < self.end_date

        return False


# ... (Signal receivers) ...

# --- Django Signals ---

@receiver(post_save, sender=Account)
def create_user_related_models(sender, instance, created, **kwargs):
    """
    Automatically create UserProfile and default Subscription when a new Account is created.
    """
    if created:
        UserProfile.objects.create(user=instance)
        Subscription.objects.create(user=instance)  # Creates a 'free' plan by default


@receiver(post_save, sender=Account)
def save_user_profile(sender, instance, **kwargs):
    """
    Automatically save the profile when the Account is saved.
    """
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=instance)