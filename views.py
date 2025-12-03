from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.urls import reverse
from .models import MembershipPlan, Trainer, GalleryImage, Admission, AdmissionPayment
from .forms import AdmissionForm, ContactForm
import qrcode, base64
from io import BytesIO
from urllib.parse import quote_plus
from decimal import Decimal


# -----------------------
# Basic pages
# -----------------------
def home(request):
    plans = MembershipPlan.objects.all()[:3]
    trainers = Trainer.objects.all()[:4]
    gallery = GalleryImage.objects.all()[:6]
    return render(
        request,
        'body/home.html',
        {'plans': plans, 'trainers': trainers, 'gallery': gallery}
    )


def bmi_bmr_view(request):
    return render(request, "body/bmi_bmr.html")


def about(request):
    return render(request, 'body/about.html')


def plans(request):
    plans = MembershipPlan.objects.all()
    return render(request, 'body/plans.html', {'plans': plans})


def trainers_view(request):
    trainers = Trainer.objects.all()
    return render(request, 'body/trainers.html', {'trainers': trainers})


def gallery(request):
    images = GalleryImage.objects.all()
    return render(request, 'body/gallery.html', {'images': images})


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            messages.success(request, 'Thanks — your message was sent!')
            return redirect('body:contact')
    else:
        form = ContactForm()
    return render(request, 'body/contact.html', {'form': form})

def profile(request):
    return render(request, 'body/profile.html')

# -----------------------
# Admission
# -----------------------
def admission_form(request):
    """
    Admission view:
    - Shows form
    - Saves Admission
    - Forces correct plan + duration
    """

    plans = MembershipPlan.objects.all()
    selected_plan_id = request.POST.get("plan")

    if request.method == 'POST':
        post_data = request.POST.copy()
        if selected_plan_id:
            post_data["plan"] = selected_plan_id

        form = AdmissionForm(post_data, request.FILES)

        if form.is_valid():
            admission = form.save(commit=False)

            if admission.plan:
                try:
                    months = int(admission.duration_months)
                except:
                    months = 1
                admission.total_amount = admission.plan.price_month * Decimal(months)
            else:
                admission.total_amount = Decimal('0.00')

            admission.save()

            messages.success(request, "Application submitted — continue to payment.")
            return redirect('body:payment_form', admission_id=admission.id)

        messages.error(request, 'Fix the errors and try again.')
    else:
        form = AdmissionForm()

    return render(
        request,
        'body/admission_form.html',
        {'form': form, 'plans': plans}
    )


# -----------------------
# Payment flow
# -----------------------
def payment_form(request, admission_id):
    admission = get_object_or_404(Admission, id=admission_id)

    if not admission.plan or admission.total_amount <= Decimal('0.00'):
        messages.error(request, "Invalid plan or payment amount.")
        return redirect('body:admission_form')

    return render(
        request,
        'body/payment_form.html',
        {'admission': admission}
    )


def upi_redirect(request, admission_id):
    if request.method != "POST":
        return redirect('body:payment_form', admission_id=admission_id)

    admission = get_object_or_404(Admission, id=admission_id)

    if not admission.plan:
        messages.error(request, "Plan missing. Contact admin.")
        return redirect('body:payment_form', admission_id=admission.id)

    amount_decimal = admission.total_amount or Decimal('0.00')
    if amount_decimal <= 0:
        messages.error(request, "Invalid payment amount.")
        return redirect('body:payment_form', admission_id=admission.id)

    amount_str = str(amount_decimal)

    # Create payment record
    with transaction.atomic():
        payment = AdmissionPayment.objects.create(
            admission=admission,
            amount=amount_decimal,
            payment_mode="UPI",
            status="pending"
        )

    # UPI Deep-Link
    UPI_ID = "yuvrajprajapati5665@okhdfcbank"
    merchant_name = "GYM-SHIM"
    note = f"Admission-{admission.id}"

    upi_link = (
        f"upi://pay?pa={quote_plus(UPI_ID)}"
        f"&pn={quote_plus(merchant_name)}"
        f"&am={quote_plus(amount_str)}"
        f"&tn={quote_plus(note)}"
        f"&tr={quote_plus(str(payment.transaction_id))}"
        f"&cu=INR"
    )

    # QR Code
    qr_img = qrcode.make(upi_link)
    buf = BytesIO()
    qr_img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    # Mobile → redirect to UPI app
    agent = request.META.get("HTTP_USER_AGENT", "").lower()
    if any(k in agent for k in ("mobi", "android", "iphone")):
        return redirect(upi_link)

    # Desktop → show QR page
    return render(
        request,
        'body/upi_redirect.html',
        {
            "upi_link": upi_link,
            "amount": amount_str,
            "qr_code": qr_b64,
            "payment": payment,
            "admission": admission,
        }
    )


def confirm_payment(request, payment_id):
    if request.method != "POST":
        return redirect('body:home')

    payment = get_object_or_404(AdmissionPayment, id=payment_id)

    if payment.status != "pending":
        messages.info(request, "Payment already processed.")
        return redirect('body:payment_success')

    upi_txn_ref = request.POST.get("upi_txn_ref", "").strip()

    if not (4 <= len(upi_txn_ref) <= 128) or any(c.isspace() for c in upi_txn_ref):
        messages.error(request, "Enter a valid transaction reference.")
        return redirect('body:upi_redirect', admission_id=payment.admission.id)

    payment.upi_id = upi_txn_ref
    payment.status = "success"
    payment.save(update_fields=["upi_id", "status"])

    messages.success(request, "Payment verified successfully.")
    return redirect('body:payment_success')


def payment_success(request):
    return render(request, "body/payment_success.html")
