import datetime
import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.files.images import get_image_dimensions

from .models import Admission, AdmissionPayment, MembershipPlan


class AdmissionForm(forms.ModelForm):
    """
    Admission form synced with the full Admission model, 
    including gender and all required fields.
    """

    upi_id = forms.CharField(
        max_length=100,
        required=False,
        help_text="Enter your UPI ID (e.g. name@upi)",
        widget=forms.TextInput(attrs={'placeholder': 'example@upi', 'class': 'form-control'})
    )

    plan = forms.ModelChoiceField(
        queryset=MembershipPlan.objects.all(),
        empty_label=None,
        required=True,
        help_text="Choose your membership plan",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    gender = forms.ChoiceField(
    choices=[
        ('', 'Prefer not to say'),
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other'),
    ],
    required=False
         )

    class Meta:
        model = Admission
        fields = [
            'first_name', 'last_name', 'gender', 'email', 'phone',
            'date_of_birth', 'address', 'plan', 'start_date',
            'duration_months', 'emergency_contact_name',
            'emergency_contact_phone', 'fitness_goals',
            'medical_conditions', 'photo', 'upi_id', 'agreed_terms'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'duration_months': forms.NumberInput(attrs={'class': 'form-control'}),
            'emergency_contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'emergency_contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'fitness_goals': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'medical_conditions': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'photo': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'agreed_terms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    # VALIDATIONS ---------------------------------------------------

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError('Enter a valid email address.')
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        sanitized = phone.replace("-", "").replace(" ", "")
        if not re.match(r'^\+?\d{7,15}$', sanitized):
            raise ValidationError('Enter a valid phone number (7–15 digits).')
        return phone

    def clean_emergency_contact_phone(self):
        phone = (self.cleaned_data.get('emergency_contact_phone') or '').strip()
        if phone:
            sanitized = phone.replace("-", "").replace(" ", "")
            if not re.match(r'^\+?\d{7,15}$', sanitized):
                raise ValidationError('Enter a valid emergency contact number (7–15 digits).')
        return phone

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = datetime.date.today()
            age = (today - dob).days / 365.2425
            if age < 14:
                raise ValidationError('Applicant must be at least 14 years old.')
        return dob

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date and start_date < datetime.date.today():
            raise ValidationError('Start date cannot be in the past.')
        return start_date

    

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            if photo.size > 4 * 1024 * 1024:
                raise ValidationError('Photo file is too large (max 4MB).')
            if not getattr(photo, 'content_type', '').startswith('image/'):
                raise ValidationError('Only image files are allowed.')
            width, height = get_image_dimensions(photo)
            if width < 200 or height < 200:
                raise ValidationError('Image is too small (minimum 200x200px).')
        return photo

    def clean_upi_id(self):
        upi_id = (self.cleaned_data.get('upi_id') or '').strip()
        if upi_id and not re.match(r'^[\w.-]+@[\w]+$', upi_id):
            raise ValidationError('Enter a valid UPI ID (example@upi).')
        return upi_id

    def clean_agreed_terms(self):
        agreed = self.cleaned_data.get('agreed_terms')
        if not agreed:
            raise ValidationError('You must agree to the terms and conditions.')
        return agreed

    # SAVE ----------------------------------------------------------

    def save(self, commit=True):
        admission = super().save(commit=False)

        if admission.plan:
            admission.total_amount = (
                Decimal(admission.plan.price_month) * Decimal(admission.duration_months)
            )
        else:
            admission.total_amount = Decimal('0.00')

        if commit:
            admission.save()
        return admission


# PAYMENT FORM -----------------------------------------------------
class PaymentForm(forms.ModelForm):
    class Meta:
        model = AdmissionPayment
        fields = ['amount', 'payment_mode', 'upi_id']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'readonly': True}),
            'payment_mode': forms.Select(attrs={'class': 'form-control'}),
            'upi_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'example@upi'}),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not amount or amount <= 0:
            raise ValidationError('Invalid payment amount.')
        return amount

    def clean_upi_id(self):
        upi_id = (self.cleaned_data.get('upi_id') or '').strip()
        if upi_id and not re.match(r'^[\w.-]+@[\w]+$', upi_id):
            raise ValidationError('Enter a valid UPI ID.')
        return upi_id


# CONTACT FORM -----------------------------------------------------
class ContactForm(forms.Form):
    name = forms.CharField(max_length=120, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}))
