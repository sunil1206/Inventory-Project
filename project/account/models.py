from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db.models.signals import post_save
from django.dispatch import receiver


# --- Custom User Manager ---

class MyAccountManager(BaseUserManager):
    """
    This is the manager for our custom Account model.
    It defines how users (create_user) and superusers (create_superuser)
    are created.
    """

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
        # A superuser has all permissions
        user.is_admin = True
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user


# --- Custom User Model ---

class Account(AbstractBaseUser):
    """
    This is our custom user model, which replaces the default Django User.
    It uses email as the primary login field.
    """
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    username = models.CharField(max_length=50, unique=True)
    email = models.EmailField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=50, blank=True)  # Good to have

    # Required fields for Django's admin
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)  # Set to False by default for email activation
    is_superuser = models.BooleanField(default=False)

    # Tell Django which field to use for logging in
    USERNAME_FIELD = 'email'

    # Fields required when creating a user via command line (createsuperuser)
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    objects = MyAccountManager()

    def __str__(self):
        return self.email

    def has_perm(self, perm, obj=None):
        "Does the user have a specific permission?"
        # Simplest possible answer: Yes, always if they are an admin
        return self.is_admin

    def has_module_perms(self, app_label):
        "Does the user have permissions to view the app `app_label`?"
        # Simplest possible answer: Yes, always
        return True


# --- User Profile Model ---

class UserProfile(models.Model):
    """
    This model holds extra information about a user.
    It has a one-to-one relationship with the Account model.
    """
    user = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='userprofile/', blank=True, null=True)
    address_line_1 = models.CharField(max_length=100, blank=True)
    address_line_2 = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=50, blank=True)
    state = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.user.first_name

    def get_full_address(self):
        return f'{self.address_line_1}, {self.city}, {self.state}'

    def delete_profile_picture(self):
        """
        This is the method called by your 'edit_profile' view.
        It deletes the physical file from storage.
        """
        if self.profile_picture:
            self.profile_picture.delete(save=True)
            self.profile_picture = None
            self.save()


# --- Django Signals ---

@receiver(post_save, sender=Account)
def create_user_profile(sender, instance, created, **kwargs):
    """
    This signal automatically creates a UserProfile object
    whenever a new Account is created.
    """
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=Account)
def save_user_profile(sender, instance, **kwargs):
    """
    This signal automatically saves the profile
    whenever the Account object is saved.
    """
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        # This handles cases for existing users made before the signal was created
        UserProfile.objects.create(user=instance)