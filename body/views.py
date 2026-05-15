from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.db.models import Sum, Q, F

from .models import (
    MembershipPlan, Trainer, GalleryImage, Admission, 
    AdmissionPayment, Product, Sale, ProductOrder
)
from .forms import AdmissionForm, ContactForm

import qrcode, base64
from io import BytesIO
from urllib.parse import quote_plus
from decimal import Decimal

from .models import (
    MembershipPlan, Trainer, GalleryImage, Admission,
    AdmissionPayment, Product, Sale, ProductOrder, UserAddress
)



def add_address(request):
    if request.method == "POST" and request.user.is_authenticated:
        is_default = request.POST.get('is_default') == 'on'
        # If this is being set as default, clear existing default first
        if is_default:
            UserAddress.objects.filter(user=request.user).update(is_default=False)
        UserAddress.objects.create(
            user       = request.user,
            full_name  = request.POST.get('full_name', ''),
            phone      = request.POST.get('phone', ''),
            line1      = request.POST.get('line1', ''),
            city       = request.POST.get('city', ''),
            state      = request.POST.get('state', ''),
            pincode    = request.POST.get('pincode', ''),
            type       = request.POST.get('type', 'Home'),
            is_default = is_default,
        )
        messages.success(request, "Address saved.")
    return redirect('body:profile')

def submit_feedback(request):
    if request.method == "POST" and request.user.is_authenticated:
        # If you have a Feedback model, save it here later
        # For now just show a success message
        messages.success(request, "Feedback received. Thank you!")
    return redirect('body:profile')


def delete_address(request, addr_id):
    if request.user.is_authenticated:
        UserAddress.objects.filter(id=addr_id, user=request.user).delete()
        messages.success(request, "Address removed.")
    return redirect('body:profile')


def set_default_address(request, addr_id):
    if request.user.is_authenticated:
        UserAddress.objects.filter(user=request.user).update(is_default=False)
        UserAddress.objects.filter(id=addr_id, user=request.user).update(is_default=True)
        messages.success(request, "Default address updated.")
    return redirect('body:profile')


def change_password(request):
    if request.method == "POST" and request.user.is_authenticated:
        from django.contrib.auth import update_session_auth_hash
        old  = request.POST.get('old_password')
        new1 = request.POST.get('new_password1')
        new2 = request.POST.get('new_password2')
        if new1 != new2:
            messages.error(request, "New passwords don't match.")
        elif not request.user.check_password(old):
            messages.error(request, "Current password is incorrect.")
        else:
            request.user.set_password(new1)
            request.user.save()
            update_session_auth_hash(request, request.user)  # keeps user logged in
            messages.success(request, "Password updated successfully.")
    return redirect('body:profile')

# -------------------------------------------------------------------------
# 1. AUTHENTICATION & IDENTITY GATEWAY
# -------------------------------------------------------------------------

def auth_view(request):
    """
    Handles Real-Time User Creation and Authentication.
    Connects frontend forms to the Django User Database.
    """
    if request.method == "POST":
        action = request.POST.get('action')
        
        if action == "signup":
            first_name = request.POST.get('first_name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            
            if not email or not password:
                messages.error(request, "Credentials cannot be empty.")
                return redirect('body:profile')

            if User.objects.filter(username=email).exists():
                messages.error(request, "Email already registered.")
                return redirect('body:profile')

            user = User.objects.create_user(username=email, email=email, password=password)
            user.first_name = first_name
            user.save()
            
            login(request, user)
            messages.success(request, f"Welcome, {first_name}!")
            return redirect('body:profile')

        elif action == "login":
            email = request.POST.get('email')
            password = request.POST.get('password')
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                return redirect('body:profile')
            else:
                messages.error(request, "Invalid Credentials.")
                return redirect('body:profile')
                
    return redirect('body:profile')

def logout_view(request):
    logout(request)
    messages.info(request, "Session Terminated.")
    return redirect('body:home')

# -------------------------------------------------------------------------
# 2. ELITE COMMAND CENTER (PROFILE) - FIXED REDIRECT LOOP
# -------------------------------------------------------------------------

def profile_view(request):
    """
    Sovereign Command Center: Synchronizes User session with DB records.
    NO @login_required here to prevent infinite redirect loops.
    """
    # 1. If not logged in, just show the page. 
    # Template {% if not user.is_authenticated %} handles the login form display.
    if not request.user.is_authenticated:
        return render(request, 'body/profile.html')

    # 2. If logged in, fetch data for the dashboard
    email = request.user.email
    admission = Admission.objects.filter(email=email).first()
    orders = ProductOrder.objects.filter(email=email).order_by('-created_at')
    payments = AdmissionPayment.objects.filter(admission__email=email).order_by('-created_at')
    
    total_spent = payments.filter(status='success').aggregate(Sum('amount'))['amount__sum'] or 0
    
    context = {
        'orders': orders,
        'payments': payments,
        'admission': admission,
        'latest_order': orders.first(),
        'total_spent': total_spent,
        'order_count': orders.count(),
        'attendance_rate': 82 if admission else 0,
        'streak_days': 14 if admission else 0,
    }
    return render(request, 'body/profile.html', context)

def update_profile(request):
    if request.method == "POST" and request.user.is_authenticated:
        u = request.user
        u.first_name = request.POST.get('first_name', u.first_name)
        u.email = request.POST.get('email', u.email)
        u.save()
        messages.success(request, "Profile Updated.")
    return redirect('body:profile')

# -------------------------------------------------------------------------
# 3. CORE CONTENT
# -------------------------------------------------------------------------

def home(request):
    return render(request, 'body/home.html', {
        'plans': MembershipPlan.objects.all().order_by('-is_popular')[:3],
        'trainers': Trainer.objects.filter(is_active=True)[:4],
        'gallery': GalleryImage.objects.all().order_by('-uploaded_at')[:6]
    })

def about(request): return render(request, 'body/about.html')
def bmi_bmr_view(request): return render(request, "body/bmi_bmr.html")

def plans_catalog(request):
    return render(request, 'body/plans.html', {'plans': MembershipPlan.objects.all()})

def trainers_view(request):
    return render(request, 'body/trainers.html', {'trainers': Trainer.objects.filter(is_active=True)})

def gallery_view(request):
    return render(request, 'body/gallery.html', {'images': GalleryImage.objects.all()})

# -------------------------------------------------------------------------
# 4. IMS FLOW
# -------------------------------------------------------------------------

def shop(request):
    return render(request, 'body/shop.html', {'products': Product.objects.all()})

def checkout(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    # 1. Stock Validation
    if product.stock <= 0:
        messages.error(request, "This item is currently sold out.")
        return redirect('body:shop')

    if request.method == "POST":
        try:
            # 2. Extract Data
            full_name = request.POST.get('full_name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            address = request.POST.get('address')

            # 3. Save Order (Atomic)
            # We save the order as 'pending'. 
            # We DON'T create a Sale record until the payment is confirmed.
            with transaction.atomic():
                order = ProductOrder.objects.create(
                    product=product,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    address=address,
                    total_amount=product.price,
                    status='pending'
                )

            # 4. Generate UPI Payment Data
            # Note: amount must be a string for f-strings
            upi_link = f"upi://pay?pa=yuvrajprajapati5665@okhdfcbank&pn=GYMSHIM&am={product.price}&cu=INR"
            
            # QR Code Generation
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(upi_link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            buf = BytesIO()
            img.save(buf, format="PNG")
            qr_base64 = base64.b64encode(buf.getvalue()).decode()
            
            # 5. Redirect to UPI / QR Page
            return render(request, 'body/upi_redirect.html', {
                'payment_title': f'Payment for {product.name}',
                'qr_code': qr_base64,
                'upi_link': upi_link, # For direct mobile deep-linking
                'amount': product.price,
                'order_id': order.id,
                'confirm_url': reverse('body:payment_success')
            })

        except Exception as e:
            messages.error(request, f"System Error: {str(e)}")
            return redirect('body:shop')

    # Initial GET Request: Fetch saved profile data if exists
    user_profile = getattr(request.user, 'profile', None)
    context = {
        'product': product,
        'user_phone': user_profile.phone if user_profile else "+91",
        'user_address': user_profile.address if user_profile else ""
    }
    
    return render(request, 'body/checkout.html', context)

# -------------------------------------------------------------------------
# 5. CRM FLOW
# -------------------------------------------------------------------------

def admission_form(request):
    if request.method == 'POST':
        form = AdmissionForm(request.POST, request.FILES)
        if form.is_valid():
            adm = form.save(commit=False)
            months = int(request.POST.get('duration_months', 1))
            adm.total_amount = adm.plan.price_month * Decimal(months)
            adm.save()
            return redirect('body:payment_form', admission_id=adm.id)
    return render(request, 'body/admission_form.html', {'form': AdmissionForm(), 'plans': MembershipPlan.objects.all()})

def payment_form(request, admission_id):
    return render(request, 'body/payment_form.html', {'admission': get_object_or_404(Admission, id=admission_id)})

def upi_redirect(request, admission_id):
    adm = get_object_or_404(Admission, id=admission_id)
    AdmissionPayment.objects.create(admission=adm, amount=adm.total_amount)
    upi_link = f"upi://pay?pa=yuvrajprajapati5665-1@okaxis&pn=GYMSHIM&am={adm.total_amount}&cu=INR"
    qr_img = qrcode.make(upi_link)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    return render(request, 'body/upi_redirect.html', {
        'payment_title': 'Membership', 'qr_code': base64.b64encode(buf.getvalue()).decode(),
        'amount': adm.total_amount, 'confirm_url': reverse('body:payment_success')
    })

def confirm_payment(request, payment_id):
    p = get_object_or_404(AdmissionPayment, id=payment_id)
    p.upi_id, p.status = request.POST.get("upi_txn_ref"), "success"
    p.save()
    return redirect('body:payment_success')

def payment_success(request): return render(request, "body/payment_success.html")

def contact(request):
    if request.method == 'POST': messages.success(request, 'SOS Received.')
    return render(request, 'body/contact.html', {'form': ContactForm()})

def update_profile(request):
    if request.method == "POST":
        u = request.user
        u.first_name = request.POST.get('first_name')
        u.email = request.POST.get('email')
        if 'pfp' in request.FILES:
            u.profile_image = request.FILES['pfp'] # Requires profile_image field in User/Profile model
        u.save()
        messages.success(request, "Identity Protocols Updated.")
    return redirect('body:profile')