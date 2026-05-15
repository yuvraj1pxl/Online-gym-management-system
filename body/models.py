from decimal import Decimal
import uuid
from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User

# -------------------------
# MEMBERSHIP & ADMISSION
# -------------------------

class MembershipPlan(models.Model):
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
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
        ('', 'Prefer not to say'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.TextField(blank=True)

    plan = models.ForeignKey(MembershipPlan, on_delete=models.SET_NULL, null=True, related_name='admissions')
    start_date = models.DateField(default=timezone.now)
    duration_months = models.PositiveIntegerField(default=1) 

    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    fitness_goals = models.TextField(blank=True)
    medical_conditions = models.TextField(blank=True)

    photo = models.ImageField(upload_to='admissions/photos/%Y/%m/%d/', blank=True, null=True)
    upi_id = models.CharField(max_length=100, blank=True)
    agreed_terms = models.BooleanField(default=False)
    
    # Financial field used by your template
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    # --- SERVER-SIDE PRICE CALCULATION ---
    def save(self, *args, **kwargs):
        if self.plan:
            # Logic: Monthly Rate x Number of Months
            self.total_amount = self.plan.price_month * self.duration_months
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} — {self.email}"


class AdmissionPayment(models.Model):
    PAYMENT_STATUS = [('pending', 'Pending'), ('success', 'Success'), ('failed', 'Failed')]
    PAYMENT_MODE = [('UPI', 'UPI'), ('Card', 'Card'), ('Other', 'Other')]

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


# -------------------------
# INVENTORY & SALES (IMS)
# -------------------------

class Product(models.Model):
    # 1. Define the choices first
    CATEGORY_CHOICES = [
        ('Supplements', 'Supplements'),
        ('Gear', 'Gear'),
        ('Apparel', 'Apparel'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image_url = models.URLField(max_length=500, blank=True, help_text="Link to product image")
    
    # 2. Add the actual category field here
    category = models.CharField(
        max_length=20, 
        choices=CATEGORY_CHOICES, 
        default='Gear'
    )

    def __str__(self):
        return f"{self.name} ({self.category})"


class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sales')
    quantity = models.PositiveIntegerField(default=1)
    timestamp = models.DateTimeField(auto_now_add=True)

    # --- STOCK INTEGRITY LOGIC ---
    def save(self, *args, **kwargs):
        if not self.pk: # Only on creation
            if self.product.stock >= self.quantity:
                self.product.stock -= self.quantity
                self.product.save()
            else:
                raise ValueError("Insufficient stock for this sale.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale: {self.product.name} x {self.quantity}"


class ProductOrder(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid / Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders')
    full_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    address = models.TextField(help_text="Full delivery address")
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    upi_ref = models.CharField(max_length=100, blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} - {self.product.name} ({self.full_name})"


# -------------------------
# CONTENT & MEDIA
# -------------------------

class Trainer(models.Model):
    name = models.CharField(max_length=120)
    specialization = models.CharField(max_length=200)
    bio_short = models.TextField(default="", max_length=200)
    bio_full = models.TextField(default="")
    image_url = models.URLField(max_length=500)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return f"{self.name} - {self.specialization}"


class GalleryImage(models.Model):
    title = models.CharField(max_length=200, blank=True)
    image = models.ImageField(upload_to='gallery/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title or str(self.image.name)


class UserAddress(models.Model):   # ← correct: top-level, not indented
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name='addresses')
    full_name  = models.CharField(max_length=100)
    phone      = models.CharField(max_length=15)
    line1      = models.CharField(max_length=200)
    city       = models.CharField(max_length=80)
    state      = models.CharField(max_length=80)
    pincode    = models.CharField(max_length=10)
    type       = models.CharField(max_length=20, default='Home')
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.full_name} — {self.city}"


# -------------------------
# SIGNALS
# -------------------------
@receiver(post_migrate)
def create_default_plans(sender, **kwargs):
    if sender.name == 'body':
        default_plans = [
            {"name": "Basic", "price_month": 999, "price_annual": 9590},
            {"name": "Premium", "price_month": 1999, "price_annual": 19180},
            {"name": "Elite", "price_month": 2999, "price_annual": 28770},
        ]
        for plan in default_plans:
            MembershipPlan.objects.get_or_create(name=plan['name'], defaults=plan)