from decimal import Decimal
import uuid

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.db.models.signals import post_migrate
from django.dispatch import receiver


class MembershipPlan(models.Model):
    """
    Stores membership plans (Basic, Premium, Elite).
    Fields used in templates: name, price_month, price_annual, duration_days, perks, slug, is_popular
    """
    name = models.CharField(max_length=100, unique=True)
    price_month = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('999.00'))
    price_annual = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('9590.00'))
    duration_days = models.PositiveIntegerField(default=30)
    perks = models.TextField(blank=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    is_popular = models.BooleanField(default=False)

    class Meta:
        ordering = ['-is_popular', 'price_month', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)[:70]
            slug = base_slug
            counter = 1
            while MembershipPlan.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (₹{self.price_month}/mo)"


class Admission(models.Model):
    """
    Represents a member's admission form entry.
    Fully aligned with your template fields.
    """

    # Personal Info
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    gender = models.CharField(
        max_length=10,
        choices=[("Male", "Male"), ("Female", "Female"), ("Other", "Other")],
        blank=True
    )
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    # Membership Details
    plan = models.ForeignKey(MembershipPlan, on_delete=models.SET_NULL, null=True, related_name='admissions')
    start_date = models.DateField(default=timezone.now)
    duration_months = models.PositiveIntegerField(default=1) 

    # Emergency Contact
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    # Additional Info
    fitness_goals = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)

    # Photo & Payment Details
    photo = models.ImageField(upload_to='admissions/photos/%Y/%m/%d/', blank=True, null=True)
    upi_id = models.CharField(max_length=100, blank=True)

    # Agreement
    agreed_terms = models.BooleanField(default=False)

    # Pricing Total (based on plan)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    GENDER_CHOICES = [
    ('male', 'Male'),
    ('female', 'Female'),
    ('other', 'Other'),
    ('', 'Prefer not to say'),
]

    gender = models.CharField(
    max_length=10,
    choices=GENDER_CHOICES,
    blank=True,
    null=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.email}"


class AdmissionPayment(models.Model):
    """
    Tracks payments made against an admission.
    """
    PAYMENT_STATUS = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    PAYMENT_MODE = [
        ('UPI', 'UPI'),
        ('Card', 'Card'),
        ('Other', 'Other'),
    ]

    admission = models.ForeignKey(Admission, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    upi_id = models.CharField(max_length=100, blank=True)
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODE, default='UPI')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment {self.transaction_id} — {self.status} — ₹{self.amount}"


class Trainer(models.Model):
    # Basic Info
    name = models.CharField(max_length=120)
    specialization = models.CharField(max_length=200, help_text="e.g., Strength & Conditioning • Powerlifting")
    
    # Bio sections
    bio_short = models.TextField(
        default="",
        help_text="Short preview bio (1 sentence)",
        max_length=200
    )
    bio_full = models.TextField(
        default="",
        help_text="Full detailed bio (shows when 'Read more' is clicked)"
    )
    
    # Image
    image_url = models.URLField(
        max_length=500,
        help_text="Full URL to trainer image (Pinterest, CDN, etc.)"
    )
    
    # Display Order
    order = models.PositiveIntegerField(
        default=0,
        help_text="Lower numbers appear first (0, 1, 2, 3, 4, 5)"
    )
    
    # Active Status
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this trainer from the website"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = "Trainer"
        verbose_name_plural = "Trainers"

    def __str__(self):
        return f"{self.name} - {self.specialization}"


class GalleryImage(models.Model):
    title = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='gallery/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or str(self.image.name)


# -------------------------
# AUTO-CREATE DEFAULT PLANS
# -------------------------
@receiver(post_migrate)
def create_default_plans(sender, **kwargs):
    if sender.name == 'body':  # run only for your app
        default_plans = [
            {"name": "Basic", "price_month": 999, "price_annual": 9590},
            {"name": "Premium", "price_month": 1999, "price_annual": 19180},
            {"name": "Elite", "price_month": 2999, "price_annual": 28770},
        ]
        for plan in default_plans:
            MembershipPlan.objects.get_or_create(name=plan['name'], defaults=plan)
