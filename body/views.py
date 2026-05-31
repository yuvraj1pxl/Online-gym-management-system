import json  # Ensure json is imported at the top of your file
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
            phone = request.POST.get('phone', '')
            line1 = request.POST.get('line1', '')
            city = request.POST.get('city', '')
            state = request.POST.get('state', '')
            pincode = request.POST.get('pincode', '')
            
            if not email or not password:
                messages.error(request, "Credentials cannot be empty.")
                next_url = request.POST.get('next') or 'body:profile'
                return redirect(next_url)

            if User.objects.filter(username=email).exists():
                messages.error(request, "Email already registered.")
                next_url = request.POST.get('next') or 'body:profile'
                return redirect(next_url)

            user = User.objects.create_user(username=email, email=email, password=password)
            user.first_name = first_name
            user.save()
            
            # Sync Phone in UserProfile
            from .models import UserProfile
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if phone:
                profile.phone = phone
                profile.save()
            
            # Sync Address in UserAddress
            if line1 or city or state or pincode:
                from .models import UserAddress
                UserAddress.objects.create(
                    user=user,
                    full_name=first_name,
                    phone=phone,
                    line1=line1,
                    city=city,
                    state=state,
                    pincode=pincode,
                    is_default=True
                )
            
            login(request, user)
            messages.success(request, f"Welcome, {first_name}!")
            
            next_url = request.POST.get('next') or 'body:profile'
            return redirect(next_url)

        elif action == "login":
            email = request.POST.get('email')
            password = request.POST.get('password')
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                next_url = request.POST.get('next') or 'body:profile'
                return redirect(next_url)
            else:
                messages.error(request, "Invalid Credentials.")
                next_url = request.POST.get('next') or 'body:profile'
                return redirect(next_url)
                
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



# -------------------------------------------------------------------------
# 3. CORE CONTENT
# -------------------------------------------------------------------------

def home(request):
    premium_images = [
        {"url": "https://i.pinimg.com/1200x/6b/c8/09/6bc809a2c621357898758653237b0cce.jpg", "title": "Push Day — Intensity"},
        {"url": "https://i.pinimg.com/736x/a5/b9/02/a5b9020bfd1057d1221cb4c0f895152a.jpg", "title": "Olympic Racks"},
        {"url": "https://i.pinimg.com/1200x/b3/90/b6/b390b62285319aa1ce088c9b2c50a502.jpg", "title": "Member Transformation"},
        {"url": "https://i.pinimg.com/1200x/ab/e1/51/abe151f0e03a85ef1947fbaac5e44362.jpg", "title": "Community Event"},
        {"url": "https://i.pinimg.com/1200x/3f/74/5b/3f745bae25d8e8b619f6bf7cca737d2f.jpg", "title": "Functional Training"},
        {"url": "https://i.pinimg.com/1200x/ff/4a/7f/ff4a7f28e203e8b4192b14a92ab021ea.jpg", "title": "Member Spotlight"},
        {"url": "https://i.pinimg.com/736x/eb/66/a1/eb66a11e255d4394647c3c867e465f11.jpg", "title": "Kettlebell Zone"},
        {"url": "https://i.pinimg.com/736x/7d/cf/2d/7dcf2d7d28d966f30796bfcc078b981d.jpg", "title": "Fitness Challenge"},
        {"url": "https://i.pinimg.com/1200x/df/0d/e1/df0de1a56f952d748f654e1e18f8202a.jpg", "title": "HIIT Session"},
        {"url": "https://i.pinimg.com/736x/fe/ce/c9/fecec9f60eb91d941496fecbd9639e1a.jpg", "title": "Healthy Fuel Bar"},
        {"url": "https://i.pinimg.com/1200x/c0/17/60/c01760924cfc783be218da6d340289a3.jpg", "title": "Cardio Deck"},
        {"url": "https://i.pinimg.com/736x/0e/b8/7c/0eb87c24b36306a5c6c1d34c6334db09.jpg", "title": "Transformation Journey"},
        {"url": "https://i.pinimg.com/736x/ff/29/eb/ff29eb497698e42efbad9c5cbc0876e2.jpg", "title": "Yoga Flow"},
        {"url": "https://i.pinimg.com/736x/74/93/a8/7493a8d02345d614314deba30735e6e9.jpg", "title": "Powerlifting Meet"},
        {"url": "https://i.pinimg.com/736x/68/5f/dd/685fdd7a80c478d9e769078927db9586.jpg", "title": "Battle Ropes"},
        {"url": "https://i.pinimg.com/736x/22/e3/91/22e3915f07e3547ece6b2072813d51e7.jpg", "title": "Team Spirit"}
    ]
    return render(request, 'body/home.html', {
        'plans': MembershipPlan.objects.all().order_by('-is_popular')[:3],
        'trainers': Trainer.objects.filter(is_active=True)[:4],
        'gallery': premium_images,
        'products': Product.objects.all()[:3]
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
            upi_link = f"upi://pay?pa=yuvrajprajapati5665-1@okaxis&pn=GYMSHIM&am={product.price}&cu=INR"
            
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
                'confirm_url': reverse('body:confirm_order_payment', kwargs={'order_id': order.id})
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f"System Error: {str(e)}")
            return redirect('body:shop')

    # Initial GET Request: Fetch saved address data from UserAddress if exists
    user_phone = "+91"
    user_address = ""
    if request.user.is_authenticated:
        addr = request.user.addresses.filter(is_default=True).first() or request.user.addresses.first()
        if addr:
            user_phone = addr.phone
            user_address = f"{addr.line1}, {addr.city}, {addr.state} - {addr.pincode}"

    context = {
        'product': product,
        'user_phone': user_phone,
        'user_address': user_address
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
    payment = AdmissionPayment.objects.create(admission=adm, amount=adm.total_amount)
    upi_link = f"upi://pay?pa=yuvrajprajapati5665-1@okaxis&pn=GYMSHIM&am={adm.total_amount}&cu=INR"
    qr_img = qrcode.make(upi_link)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    return render(request, 'body/upi_redirect.html', {
        'payment_title': 'Membership', 
        'qr_code': base64.b64encode(buf.getvalue()).decode(),
        'amount': adm.total_amount, 
        'confirm_url': reverse('body:confirm_payment', kwargs={'payment_id': payment.id})
    })

def confirm_payment(request, payment_id):
    p = get_object_or_404(AdmissionPayment, id=payment_id)
    p.upi_id, p.status = request.POST.get("upi_txn_ref"), "success"
    p.save()
    return redirect('body:payment_success')

def confirm_order_payment(request, order_id):
    order = get_object_or_404(ProductOrder, id=order_id)
    if request.method == "POST":
        if order.status == 'pending':
            upi_ref = request.POST.get("upi_txn_ref")
            try:
                with transaction.atomic():
                    order.upi_ref = upi_ref
                    order.status = 'paid'
                    order.save()
                    
                    # Create a Sale record (which auto-decrements stock)
                    Sale.objects.create(
                        product=order.product,
                        quantity=1
                    )
                messages.success(request, "Payment verified! Your order is being processed.")
            except ValueError as e:
                messages.error(request, f"Order placement failed: {str(e)}")
                return redirect('body:shop')
        else:
            messages.info(request, "This order has already been processed.")
    return redirect('body:payment_success')

def payment_success(request): return render(request, "body/payment_success.html")

def contact(request):
    if request.method == 'POST': messages.success(request, 'SOS Received.')
    return render(request, 'body/contact.html', {'form': ContactForm()})

def update_profile(request):
    if request.method == "POST":
        u = request.user
        email = request.POST.get('email')
        if email:
            if User.objects.filter(username=email).exclude(pk=u.pk).exists():
                messages.error(request, "This email is already registered by another user.")
                return redirect('body:profile')
            u.email = email
            u.username = email
        u.first_name = request.POST.get('first_name', u.first_name)
        u.last_name = request.POST.get('last_name', u.last_name)
        u.save()

        # Handle phone saving in UserProfile
        phone = request.POST.get('phone')
        from .models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=u)
        if phone is not None:
            profile.phone = phone
            profile.save()

        # Handle cropped image from frontend (base64 data URL)
        cropped_image = request.POST.get('cropped_image')
        if cropped_image and cropped_image.startswith('data:image'):
            try:
                format, imgstr = cropped_image.split(';base64,')
                ext = format.split('/')[-1]
                from django.core.files.base import ContentFile
                import base64
                data = ContentFile(base64.b64decode(imgstr), name=f"pfp_{u.id}.{ext}")
                profile.profile_image = data
                profile.save()
            except Exception as e:
                import traceback
                traceback.print_exc()
        elif 'pfp' in request.FILES:
            profile.profile_image = request.FILES['pfp']
            profile.save()

        messages.success(request, "Identity Protocols Updated.")
    return redirect('body:profile')

import json  # Ensure json is imported at the top of your file

def admin_dashboard_view(request):
    """
    Sovereign Command Center Admin Dashboard Analytics Engine.
    Aggregates full database architecture values for Chart.js.
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "Access Denied. Administrative clearance required.")
        return redirect('body:profile')

    from .admin import get_dashboard_stats
    context = get_dashboard_stats()
    context['title'] = 'IMS Command Centre'
    return render(request, 'admin/index.html', context)