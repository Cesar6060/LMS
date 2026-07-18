from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager for User model with email as the unique identifier."""

    def create_user(self, email, password=None, **extra_fields):
        """Create and return a regular user with an email and password."""
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with an email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom User model for the gamedev platform.
    Uses email as the unique identifier instead of username.
    """
    username = None  # Remove username field
    email = models.EmailField(
        unique=True,
        help_text='Required. Enter a valid email address.'
    )
    is_instructor = models.BooleanField(
        default=False,
        help_text='Designates whether the user is an instructor.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Email is already required by USERNAME_FIELD

    class Meta:
        db_table = 'accounts_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name if full_name else self.email

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name if self.first_name else self.email.split('@')[0]


class UserPreferences(models.Model):
    """
    User preferences for customizing the platform experience.
    Auto-created when a user is created via signal.
    """
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('system', 'System'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='preferences'
    )

    # Display preferences
    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default='system'
    )
    timezone = models.CharField(
        max_length=50,
        default='America/Chicago'
    )

    # Avatar
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True
    )

    # Email notification preferences
    email_announcements = models.BooleanField(
        default=True,
        help_text='Receive email notifications for course announcements'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_userpreferences'
        verbose_name = 'User Preferences'
        verbose_name_plural = 'User Preferences'

    def __str__(self):
        return f"Preferences for {self.user.email}"
