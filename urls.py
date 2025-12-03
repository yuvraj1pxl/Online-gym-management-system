# body/urls.py
from django.urls import path
from . import views

app_name = "body"

urlpatterns = [
    # Home & basic pages
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('plans/', views.plans, name='plans'),
    path('trainers/', views.trainers_view, name='trainers'),
    path('gallery/', views.gallery, name='gallery'),
    path('contact/', views.contact, name='contact'),

    path('profile/', views.profile, name='profile'),
    
    path('bmi_bmr/', views.bmi_bmr_view, name='bmi_bmr'),

    # Admission
    path('admission/', views.admission_form, name='admission_form'),

    # Payment flow
    path('payment/<int:admission_id>/', views.payment_form, name='payment_form'),
    path('upi-redirect/<int:admission_id>/', views.upi_redirect, name='upi_redirect'),
    path('payment/confirm/<int:payment_id>/', views.confirm_payment, name='confirm_payment'),
    path('payment/success/', views.payment_success, name='payment_success'),
]
