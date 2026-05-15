from django.urls import path
from . import views

app_name = "body"

urlpatterns = [
    # --- Main Navigation ---
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('plans/', views.plans_catalog, name='plans'),
    path('trainers/', views.trainers_view, name='trainers'),
    path('gallery/', views.gallery_view, name='gallery'),
    path('contact/', views.contact, name='contact'),
    path('bmi_bmr/', views.bmi_bmr_view, name='bmi_bmr'),
     path('auth/', views.auth_view, name='auth_view'),

    # --- Elite Command Center (Profile) ---
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('logout/', views.logout_view, name='logout'), # CRITICAL FIX

    # --- Elite E-commerce / Shop Flow ---
    path('shop/', views.shop, name='shop'),
    path('shop/checkout/<int:product_id>/', views.checkout, name='checkout'),

    # --- Admission & Payment System ---
    path('admission/', views.admission_form, name='admission_form'),
    path('payment/<int:admission_id>/', views.payment_form, name='payment_form'),
    path('upi-redirect/<int:admission_id>/', views.upi_redirect, name='upi_redirect'),
    path('payment/confirm/<int:payment_id>/', views.confirm_payment, name='confirm_payment'),
    path('payment/success/', views.payment_success, name='payment_success'),
    
    path('profile/address/add/', views.add_address, name='add_address'),
path('profile/address/delete/<int:addr_id>/', views.delete_address, name='delete_address'),
path('profile/address/set-default/<int:addr_id>/', views.set_default_address, name='set_default_address'),
path('profile/change-password/', views.change_password, name='change_password'),
   path('profile/feedback/', views.submit_feedback, name='submit_feedback'),

]
