from django.contrib import admin
from django.utils.html import format_html
from .models import Admission, MembershipPlan, Trainer, GalleryImage

# -------------------- Admission Admin --------------------
@admin.register(Admission)
class AdmissionAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone', 'plan', 'start_date', 'created_at')
    list_filter = ('plan', 'start_date', 'created_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone')

# -------------------- Membership Plan Admin --------------------
@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price_month', 'price_annual', 'is_popular')
    list_filter = ('is_popular',)
    search_fields = ('name',)


# -------------------- Trainer Admin (ENHANCED) --------------------
@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'specialization', 'image_preview', 'is_active')
    list_display_links = ('name',)
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'specialization')
    ordering = ('order', 'name')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'specialization', 'is_active')
        }),
        ('Biography', {
            'fields': ('bio_short', 'bio_full'),
            'description': 'bio_short shows by default, bio_full appears when user clicks "Read more"'
        }),
        ('Image', {
            'fields': ('image_url',),
            'description': 'Paste full URL to trainer image (e.g., from Pinterest, Imgur, etc.)'
        }),
        ('Display Settings', {
            'fields': ('order',),
            'description': 'Lower numbers appear first (0=first, 5=last)'
        }),
    )
    
    def image_preview(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 8px;" />',
                obj.image_url
            )
        return "No image"
    image_preview.short_description = "Preview"

# -------------------- Gallery Image Admin --------------------
@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'image', 'uploaded_at')
    search_fields = ('title',)
    list_filter = ('uploaded_at',)
