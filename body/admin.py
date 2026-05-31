"""
admin.py — GYM-SHIM Full IMS v5.0
COMPLETE REPLACEMENT — fixes all data retrieval issues.

Key fixes:
- Proper Django 5.x admin hook (patching AdminSite class directly)
- Weekly chart shows LAST 8 WEEKS of real data, not just last 7 days
- All JSON is properly serialized with json.dumps()
- admin_dashboard_view added for the custom URL
- Handles empty DB gracefully with fallbacks
"""

import json
from collections import defaultdict
from datetime import timedelta, date
from decimal import Decimal

from django.contrib import admin
from django.contrib.admin import AdminSite
from django.utils.html import format_html
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, Max
from django.utils import timezone
from django.shortcuts import render
from django.contrib.auth.decorators import user_passes_test

try:
    from import_export.admin import ImportExportModelAdmin
except ImportError:
    ImportExportModelAdmin = admin.ModelAdmin  # graceful fallback

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

from .models import (
    Admission, MembershipPlan, Trainer, GalleryImage,
    Product, Sale, AdmissionPayment, ProductOrder, UserAddress
)


# ═══════════════════════════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════════════════════════

def _fmt(n):
    """Format number with commas, handles None/Decimal/float."""
    try:
        return f"{float(n):,.0f}"
    except (TypeError, ValueError):
        return "0"


def _safe_json(obj):
    """Convert Python object to JSON string safe for Django templates."""
    return json.dumps(obj, default=str)


# ═══════════════════════════════════════════════════════════════
#  SMART ALERT THRESHOLD ENGINE
# ═══════════════════════════════════════════════════════════════

def _compute_smart_threshold(product):
    """
    Dynamic alert threshold based on 30-day velocity.
    Fast (≥5/day)  → alert at 10 days supply
    Medium (1–5/day) → alert at 7 days supply
    Slow (<1/day)  → fixed at 3 units
    """
    thirty_days_ago = timezone.now() - timedelta(days=30)
    total_sold = Sale.objects.filter(
        product=product,
        timestamp__gte=thirty_days_ago
    ).aggregate(total=Sum('quantity'))['total'] or 0

    daily_avg = total_sold / 30.0

    if daily_avg >= 5:
        return max(int(daily_avg * 10), 10), daily_avg, 'fast', 'Fast'
    elif daily_avg >= 1:
        return max(int(daily_avg * 7), 7), daily_avg, 'med', 'Medium'
    else:
        return 3, daily_avg, 'slow', 'Slow'


def _extract_city_state(address_text):
    """Parse city/state from free-text Indian address."""
    if not address_text:
        return 'Unknown', 'Unknown'
    parts = [p.strip() for p in address_text.replace('\n', ',').split(',') if p.strip()]
    if len(parts) >= 3:
        return parts[-3], parts[-2]
    elif len(parts) == 2:
        return parts[0], parts[1]
    elif len(parts) == 1:
        return parts[0], parts[0]
    return 'Unknown', 'Unknown'


# ═══════════════════════════════════════════════════════════════
#  MASTER DATA ENGINE — feeds the dashboard template
# ═══════════════════════════════════════════════════════════════

def get_dashboard_stats():
    """
    Collects ALL live data for the IMS dashboard.
    Returns a dict ready to be merged into template context.
    Handles empty DB gracefully everywhere.
    """

    # ── 1. REVENUE ──────────────────────────────────────────────
    # Store revenue from Sales model
    sales_qs = Sale.objects.select_related('product').all()
    store_rev = sum(
        float(s.product.price) * s.quantity
        for s in sales_qs
        if s.product
    )

    # Membership revenue from confirmed payments
    membership_rev = float(
        AdmissionPayment.objects.filter(status='success')
        .aggregate(t=Sum('amount'))['t'] or 0
    )

    total_rev  = store_rev + membership_rev
    op_loss    = total_rev * 0.10
    net_profit = total_rev - op_loss

    # ── 2. COUNTS ───────────────────────────────────────────────
    total_members = Admission.objects.count()
    total_orders  = ProductOrder.objects.count()
    total_prods   = Product.objects.count()
    out_of_stock  = Product.objects.filter(stock=0).count()
    low_stock_cnt = 0  # will fill after smart thresholds

    # ── 3. WEEKLY REVENUE — LAST 8 WEEKS (not 7 days) ──────────
    # This is the fix: instead of last 7 days (which may be empty),
    # we look at the last 8 weeks so older data shows up in charts.
    weekly_labels = []
    weekly_revenue_vals = []

    for i in range(7, -1, -1):
        week_end   = timezone.now().date() - timedelta(weeks=i)
        week_start = week_end - timedelta(days=6)

        week_sales = Sale.objects.filter(
            timestamp__date__gte=week_start,
            timestamp__date__lte=week_end,
        ).select_related('product')

        week_rev = sum(
            float(s.product.price) * s.quantity
            for s in week_sales
            if s.product
        )

        # Also include membership payments in this week
        week_mem = float(
            AdmissionPayment.objects.filter(
                status='success',
                created_at__date__gte=week_start,
                created_at__date__lte=week_end,
            ).aggregate(t=Sum('amount'))['t'] or 0
        )

        weekly_labels.append(f"W{8-i}")
        weekly_revenue_vals.append(round(week_rev + week_mem))

    # ── 4. ORDERS PIPELINE ──────────────────────────────────────
    statuses_cfg = [
        ('pending',   '#C9A84C'),
        ('paid',      '#22c55e'),
        ('shipped',   '#3b82f6'),
        ('delivered', '#10b981'),
        ('cancelled', '#e84040'),
    ]
    total_o = max(total_orders, 1)
    order_pipeline = []
    for status, color in statuses_cfg:
        cnt = ProductOrder.objects.filter(status=status).count()
        pct = round((cnt / total_o) * 100)
        order_pipeline.append((status.capitalize(), cnt, color, pct))

    # ── 5. INVENTORY DETAIL + SMART THRESHOLDS ──────────────────
    products_qs = list(Product.objects.all())
    inventory_detail   = []
    inventory_json_list = []
    low_stock_cnt      = 0

    for p in products_qs:
        threshold, daily_avg, speed_class, speed_label = _compute_smart_threshold(p)
        is_alert = (p.stock <= threshold)
        if is_alert and p.stock > 0:
            low_stock_cnt += 1
        if p.stock == 0:
            low_stock_cnt += 1

        max_stock  = max(p.stock, threshold * 3, 50)
        pct        = min(int((p.stock / max_stock) * 100), 100)
        bar_color  = '#e84040' if p.stock == 0 else '#C9A84C' if is_alert else '#22c55e'

        inventory_detail.append({
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'stock': p.stock,
            'alert_threshold': threshold,
            'is_alert': is_alert,
            'pct': pct,
            'bar_color': bar_color,
        })
        inventory_json_list.append({
            'name': p.name,
            'stock': p.stock,
            'alert_threshold': threshold,
            'is_alert': is_alert,
            'category': p.category,
        })

    inventory_json = _safe_json(inventory_json_list)

    # ── 6. VELOCITY & TOP/SLOW SELLING ──────────────────────────
    # Aggregate ALL sales (not just recent) for ranking
    product_sales = defaultdict(lambda: {
        'name': '', 'category': '', 'units': 0,
        'revenue': 0.0, 'last_sale': None, 'product_obj': None
    })

    for s in Sale.objects.select_related('product').all():
        if not s.product:
            continue
        pk = s.product.id
        product_sales[pk]['name']       = s.product.name
        product_sales[pk]['category']   = s.product.category
        product_sales[pk]['units']      += s.quantity
        product_sales[pk]['revenue']    += float(s.product.price) * s.quantity
        product_sales[pk]['product_obj'] = s.product
        if not product_sales[pk]['last_sale'] or s.timestamp > product_sales[pk]['last_sale']:
            product_sales[pk]['last_sale'] = s.timestamp

    # Top selling (by units)
    sorted_by_units = sorted(
        product_sales.items(), key=lambda x: x[1]['units'], reverse=True
    )
    top_selling = []
    for pk, d in sorted_by_units[:8]:
        try:
            prod = Product.objects.get(id=pk)
            _, daily_avg, speed_class, speed_label = _compute_smart_threshold(prod)
        except Product.DoesNotExist:
            speed_class, speed_label = 'slow', 'Slow'
        top_selling.append({
            'name':       d['name'],
            'category':   d['category'],
            'units_sold': d['units'],
            'revenue':    _fmt(d['revenue']),
            'speed_class': speed_class,
            'speed_label': speed_label,
        })

    # Velocity items for smart threshold panel
    velocity_items = []
    max_daily = max((d['units'] / 30.0 for _, d in sorted_by_units[:8]), default=0.01)
    max_daily = max(max_daily, 0.01)
    for pk, d in sorted_by_units[:8]:
        daily_avg  = d['units'] / 30.0
        speed_class = 'fast' if daily_avg >= 5 else 'med' if daily_avg >= 1 else 'slow'
        speed_label = 'Fast' if speed_class == 'fast' else 'Medium' if speed_class == 'med' else 'Slow'
        vel_pct    = min(int((daily_avg / max_daily) * 100), 100)
        velocity_items.append({
            'name':        d['name'],
            'daily_avg':   round(daily_avg, 1),
            'speed_class': speed_class,
            'speed_label': speed_label,
            'vel_pct':     vel_pct,
        })

    # Slow/dead stock
    now = timezone.now()
    slow_selling = []
    sold_ids = set(product_sales.keys())
    for p in products_qs:
        if p.id not in sold_ids:
            slow_selling.append({'name': p.name, 'units_sold': 0, 'stock': p.stock, 'days_since': 999})
        else:
            d = product_sales[p.id]
            if d['units'] < 5:
                days = (now - d['last_sale']).days if d['last_sale'] else 999
                slow_selling.append({'name': p.name, 'units_sold': d['units'], 'stock': p.stock, 'days_since': days})
    slow_selling.sort(key=lambda x: x['days_since'], reverse=True)
    slow_selling = slow_selling[:6]

    # ── 7. CUSTOMERS ────────────────────────────────────────────
    email_orders = list(
        ProductOrder.objects.values('email', 'full_name')
        .annotate(order_count=Count('id'), total_spent=Sum('total_amount'))
        .order_by('-order_count')
    )

    repeat_customers   = sum(1 for e in email_orders if e['order_count'] > 1)
    one_time_customers = sum(1 for e in email_orders if e['order_count'] == 1)

    top_customers = [
        {
            'name':        e['full_name'] or e['email'],
            'email':       e['email'],
            'order_count': e['order_count'],
            'total_spent': _fmt(e['total_spent'] or 0),
        }
        for e in email_orders[:8]
    ]

    # Frequency distribution
    freq = defaultdict(int)
    for e in email_orders:
        bucket = min(e['order_count'], 5)
        freq[bucket] += 1
    freq_data = {
        'labels': ['1 order', '2 orders', '3 orders', '4 orders', '5+ orders'],
        'data':   [freq.get(i, 0) for i in range(1, 5)] + [freq.get(5, 0)],
    }

    # Buyer lifestyle from product category
    gym = corporate = casual = athlete = 0
    for order in ProductOrder.objects.select_related('product').all():
        if not order.product:
            continue
        cat = order.product.category.lower()
        if 'supplement' in cat:
            gym += 1
        elif 'apparel' in cat:
            corporate += 1
        elif 'gear' in cat:
            athlete += 1
        else:
            casual += 1
    lifestyle_data = {
        'labels': ['Gym Goers', 'Corporate', 'Casual', 'Athletes'],
        'data':   [gym, corporate, casual, athlete],
    }

    # Buyer segments
    total_buyers = max(repeat_customers + one_time_customers, 1)
    buyer_segments = [
        {'label': 'Gym Enthusiasts',    'desc': 'Bought Supplements or Gear',    'icon': 'dumbbell',    'color': '#22c55e', 'bg': 'rgba(34,197,94,0.12)',   'count': gym + athlete,              'pct': 0},
        {'label': 'Corporate / Casual', 'desc': 'Bought Apparel or mixed items', 'icon': 'briefcase',   'color': '#3b82f6', 'bg': 'rgba(59,130,246,0.12)',  'count': corporate + casual,         'pct': 0},
        {'label': 'Repeat Buyers',      'desc': 'Placed more than one order',    'icon': 'rotate',      'color': '#C9A84C', 'bg': 'rgba(201,168,76,0.12)', 'count': repeat_customers,           'pct': 0},
        {'label': 'New Customers',      'desc': 'First-time purchase only',      'icon': 'user-plus',   'color': '#a855f7', 'bg': 'rgba(168,85,247,0.12)', 'count': one_time_customers,         'pct': 0},
    ]
    max_seg = max((s['count'] for s in buyer_segments), default=1) or 1
    for s in buyer_segments:
        s['pct'] = int((s['count'] / max_seg) * 100)

    # ── 8. GEOGRAPHY ────────────────────────────────────────────
    city_data = defaultdict(lambda: {
        'orders': 0, 'revenue': 0.0, 'state': '', 'products': defaultdict(int)
    })

    for order in ProductOrder.objects.select_related('product').all():
        city, state = _extract_city_state(order.address)
        city = city.title() if city else 'Unknown'
        state = state.title() if state else 'Unknown'
        city_data[city]['orders']  += 1
        city_data[city]['revenue'] += float(order.total_amount or 0)
        city_data[city]['state']    = state
        if order.product:
            city_data[city]['products'][order.product.name] += 1

    total_rev_geo = sum(d['revenue'] for d in city_data.values()) or 1
    geo_sorted    = sorted(city_data.items(), key=lambda x: x[1]['revenue'], reverse=True)

    geo_data = []
    geo_chart_labels, geo_chart_revs, geo_chart_orders = [], [], []
    for city, d in geo_sorted[:10]:
        pct      = round((d['revenue'] / total_rev_geo) * 100)
        top_prod = max(d['products'], key=d['products'].get) if d['products'] else '—'
        geo_data.append({
            'location':   city,
            'state':      d['state'],
            'orders':     d['orders'],
            'revenue':    _fmt(d['revenue']),
            'pct':        pct,
            'top_product': top_prod,
            'users':      d['orders'],
        })
        geo_chart_labels.append(city)
        geo_chart_revs.append(round(d['revenue']))
        geo_chart_orders.append(d['orders'])

    geo_chart_data = _safe_json({
        'labels':   geo_chart_labels,
        'revenues': geo_chart_revs,
        'orders':   geo_chart_orders,
    })

    # ── 9. ABC ANALYSIS ─────────────────────────────────────────
    all_products_rev = []
    for p in products_qs:
        rev = sum(
            float(s.product.price) * s.quantity
            for s in Sale.objects.filter(product=p).select_related('product')
            if s.product
        )
        all_products_rev.append((p.name, rev))

    all_products_rev.sort(key=lambda x: x[1], reverse=True)
    grand_total_rev = sum(r for _, r in all_products_rev) or 1

    abc_items      = []
    abc_counts     = {'A': 0, 'B': 0, 'C': 0}
    abc_labels_l   = []
    abc_revenues_l = []
    abc_classes_l  = []
    cumulative_pct = 0.0

    for name, rev in all_products_rev:
        pct            = round((rev / grand_total_rev) * 100, 1)
        cumulative_pct = min(cumulative_pct + pct, 100)
        cls            = 'A' if cumulative_pct <= 70 else 'B' if cumulative_pct <= 90 else 'C'
        abc_counts[cls] += 1
        abc_items.append({
            'name':       name,
            'revenue':    _fmt(rev),
            'pct':        pct,
            'cumulative': round(cumulative_pct),
            'class':      cls,
        })
        abc_labels_l.append(name[:16] + ('…' if len(name) > 16 else ''))
        abc_revenues_l.append(round(rev))
        abc_classes_l.append(cls)

    abc_chart_data = _safe_json({
        'labels':  abc_labels_l,
        'revenue': abc_revenues_l,
        'classes': abc_classes_l,
    })

    # ── 10. REVENUE SPLIT ───────────────────────────────────────
    total_disp = total_rev or 1
    revenue_split = [
        {'label': 'Membership Sales', 'value': _fmt(membership_rev), 'color': '#C9A84C',
         'pct': round((membership_rev / total_disp) * 100)},
        {'label': 'Store / Products',  'value': _fmt(store_rev),      'color': '#22c55e',
         'pct': round((store_rev / total_disp) * 100)},
        {'label': 'Operational Loss',  'value': _fmt(op_loss),         'color': '#e84040',
         'pct': round((op_loss / total_disp) * 100)},
    ]
    donut_data = _safe_json([
        round(membership_rev) or 1,
        round(store_rev) or 1,
        round(op_loss) or 1,
    ])

    # ── 11. LIVE METRICS ────────────────────────────────────────
    avg_order_val = store_rev / max(total_orders, 1)
    live_metrics = [
        {'label': 'Avg Order Value',   'sub': 'Per store order',        'value': f"₹{avg_order_val:,.0f}",             'icon': 'cart-shopping',        'color': '#C9A84C', 'bg': 'rgba(201,168,76,0.12)'},
        {'label': 'Products In Stock', 'sub': 'Currently available',    'value': str(total_prods - out_of_stock),       'icon': 'box',                  'color': '#22c55e', 'bg': 'rgba(34,197,94,0.12)'},
        {'label': 'Out of Stock',      'sub': 'Needs restocking',       'value': str(out_of_stock),                     'icon': 'triangle-exclamation', 'color': '#e84040', 'bg': 'rgba(232,64,64,0.12)'},
        {'label': 'Low Stock Alerts',  'sub': 'Smart threshold hit',    'value': str(low_stock_cnt),                    'icon': 'bell',                 'color': '#fb923c', 'bg': 'rgba(251,146,60,0.12)'},
    ]

    # ── 12. RECENT ACTIVITY ──────────────────────────────────────
    recent_orders   = ProductOrder.objects.select_related('product').order_by('-created_at')[:7]
    recent_payments = AdmissionPayment.objects.select_related('admission').order_by('-created_at')[:4]

    # ── RETURN ───────────────────────────────────────────────────
    return {
        # KPIs — formatted display
        'total_revenue':      _fmt(total_rev),
        'net_profit':         _fmt(net_profit),
        'operational_loss':   _fmt(op_loss),
        'membership_revenue': _fmt(membership_rev),
        'store_revenue':      _fmt(store_rev),
        'total_members':      total_members,
        'total_orders':       total_orders,
        'total_products':     total_prods,
        'out_of_stock':       out_of_stock,
        'low_stock_count':    f"{low_stock_cnt:02d}",

        # Charts — JSON strings (use |safe in template)
        'weekly_revenue':     _safe_json(weekly_revenue_vals),
        'weekly_labels':      _safe_json(weekly_labels),
        'donut_data':         donut_data,
        'geo_chart_data':     geo_chart_data,
        'abc_chart_data':     abc_chart_data,
        'freq_data':          _safe_json(freq_data),
        'lifestyle_data':     _safe_json(lifestyle_data),

        # Panels
        'order_pipeline':     order_pipeline,
        'inventory_detail':   inventory_detail,
        'inventory_json':     inventory_json,
        'velocity_items':     velocity_items,
        'top_selling':        top_selling,
        'slow_selling':       slow_selling,
        'revenue_split':      revenue_split,

        # Customers
        'repeat_customers':    repeat_customers,
        'one_time_customers':  one_time_customers,
        'top_customers':       top_customers,
        'buyer_segments':      buyer_segments,

        # Geography
        'geo_data':            geo_data,

        # ABC
        'abc_items':           abc_items,
        'abc_counts':          abc_counts,

        # Misc
        'live_metrics':        live_metrics,
        'recent_orders':       recent_orders,
        'recent_payments':     recent_payments,
    }


# ═══════════════════════════════════════════════════════════════
#  DJANGO ADMIN HOOK — works with Django 5.x
#  Patches AdminSite.index at the class level so it applies
#  to the default admin.site instance automatically.
# ═══════════════════════════════════════════════════════════════

_original_admin_index = AdminSite.index

def _patched_index(self, request, extra_context=None):
    extra_context = extra_context or {}
    try:
        extra_context.update(get_dashboard_stats())
    except Exception as e:
        # Never let dashboard errors break the admin
        extra_context['dashboard_error'] = str(e)
    return _original_admin_index(self, request, extra_context)

AdminSite.index = _patched_index
admin.site.index_template = 'admin/index.html'  # your template path


# ═══════════════════════════════════════════════════════════════
#  STANDALONE DASHBOARD VIEW (for the custom URL in urls.py)
#  path('admin/dashboard/', views.admin_dashboard_view, ...)
#  Add this function to your views.py instead — see note below.
# ═══════════════════════════════════════════════════════════════

def admin_dashboard_view(request):
    """
    Standalone admin dashboard view.
    Add this to views.py and register in urls.py.
    Requires staff login.
    """
    if not request.user.is_authenticated or not request.user.is_staff:
        from django.contrib.auth.views import redirect_to_login
        return redirect_to_login(request.get_full_path())

    context = get_dashboard_stats()
    context['title'] = 'IMS Command Centre'
    return render(request, 'admin/index.html', context)


# ═══════════════════════════════════════════════════════════════
#  PDF EXPORT ACTION
# ═══════════════════════════════════════════════════════════════

def generate_pdf_report(modeladmin, request, queryset):
    if not REPORTLAB_AVAILABLE:
        modeladmin.message_user(request, "ReportLab not installed. Run: pip install reportlab", level='error')
        return

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="GymShim_Report.pdf"'
    doc  = SimpleDocTemplate(response, pagesize=letter)
    styl = getSampleStyleSheet()
    elms = [Paragraph("GYM-SHIM · BUSINESS REPORT", styl['Title']), Spacer(1, 16)]

    model_name = queryset.model.__name__
    if model_name in ['Sale', 'ProductOrder', 'AdmissionPayment']:
        data  = [["ID", "Item / Member", "Amount (₹)", "Date"]]
        total = 0.0
        for obj in queryset:
            amt  = getattr(obj, 'total_amount', None) or getattr(obj, 'amount', None)
            if amt is None and hasattr(obj, 'product') and obj.product:
                amt = obj.product.price * getattr(obj, 'quantity', 1)
            amt   = float(amt or 0)
            total += amt
            name  = obj.product.name if hasattr(obj, 'product') and obj.product else str(obj)
            dt    = obj.timestamp.strftime('%d/%m/%Y') if hasattr(obj, 'timestamp') else \
                    obj.created_at.strftime('%d/%m/%Y') if hasattr(obj, 'created_at') else '—'
            data.append([str(obj.id), name, f"{amt:,.2f}", dt])
        data.append(["", "GRAND TOTAL", f"{total:,.2f}", ""])
    else:
        data = [["ID", "Record"]]
        for obj in queryset:
            data.append([str(obj.id), str(obj)])

    tbl = Table(data, colWidths=[45, 255, 110, 85])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0),  (-1, 0),  colors.HexColor('#C9A84C')),
        ('TEXTCOLOR',  (0, 0),  (-1, 0),  colors.black),
        ('FONTNAME',   (0, 0),  (-1, 0),  'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0),  (-1, -1), 9),
        ('ALIGN',      (0, 0),  (-1, -1), 'CENTER'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.HexColor('#f9f9f9'), colors.white]),
        ('GRID',       (0, 0),  (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('FONTNAME',   (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f0ede6')),
    ]))
    elms.append(tbl)
    doc.build(elms)
    return response

generate_pdf_report.short_description = "📥 Download PDF Report"


# ═══════════════════════════════════════════════════════════════
#  MODEL ADMIN REGISTRATIONS
# ═══════════════════════════════════════════════════════════════

@admin.register(ProductOrder)
class ProductOrderAdmin(ImportExportModelAdmin):
    actions        = [generate_pdf_report]
    list_display   = ('order_id', 'full_name', 'product_link', 'amount_cell', 'status_badge', 'created_at')
    list_filter    = ('status', 'created_at', 'product__category')
    search_fields  = ('full_name', 'email', 'phone')
    ordering       = ('-created_at',)
    readonly_fields = ('transaction_id', 'created_at')
    fieldsets = (
        ('Order',    {'fields': ('product', 'status', 'total_amount', 'transaction_id')}),
        ('Customer', {'fields': ('full_name', 'email', 'phone', 'address')}),
        ('Payment',  {'fields': ('upi_ref',)}),
        ('Meta',     {'fields': ('created_at',)}),
    )

    def order_id(self, obj):
        return format_html('<b style="color:#C9A84C;font-family:monospace;">#{}</b>', obj.id)
    order_id.short_description = 'ID'

    def product_link(self, obj):
        if obj.product:
            return format_html(
                '<a href="/admin/body/product/{}/change/" style="color:#3b82f6;">{}</a>',
                obj.product.id, obj.product.name
            )
        return '—'
    product_link.short_description = 'Product'

    def amount_cell(self, obj):
        return format_html('<b style="color:#22c55e;">₹{}</b>', obj.total_amount)
    amount_cell.short_description = 'Amount'

    def status_badge(self, obj):
        palette = {
            'pending':   ('#C9A84C', '#000'),
            'paid':      ('#22c55e', '#000'),
            'shipped':   ('#3b82f6', '#fff'),
            'delivered': ('#10b981', '#fff'),
            'cancelled': ('#e84040', '#fff'),
        }
        bg, fg = palette.get(obj.status, ('#333', '#fff'))
        return format_html(
            '<span style="background:{};color:{};padding:3px 12px;border-radius:20px;'
            'font-weight:900;font-size:10px;letter-spacing:1px;">{}</span>',
            bg, fg, obj.status.upper()
        )
    status_badge.short_description = 'Status'


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display   = ('thumb', 'name', 'category_badge', 'price_cell', 'stock_bar', 'velocity_cell', 'stock_status')
    list_filter    = ('category',)
    search_fields  = ('name', 'description')
    ordering       = ('stock',)
    fieldsets = (
        ('Product',         {'fields': ('name', 'category', 'description', 'image_url')}),
        ('Pricing & Stock', {'fields': ('price', 'stock')}),
    )

    def thumb(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" style="width:36px;height:36px;border-radius:7px;object-fit:cover;">',
                obj.image_url
            )
        return '📦'
    thumb.short_description = ''

    def category_badge(self, obj):
        colors_map = {
            'Supplements': '#22c55e',
            'Gear':        '#3b82f6',
            'Apparel':     '#a855f7',
        }
        color = colors_map.get(obj.category, '#888')
        return format_html(
            '<span style="background:{}22;color:{};padding:2px 10px;border-radius:12px;font-size:10px;font-weight:800;">{}</span>',
            color, color, obj.category
        )
    category_badge.short_description = 'Category'

    def price_cell(self, obj):
        return format_html('<b style="color:#C9A84C;">₹{}</b>', obj.price)
    price_cell.short_description = 'Price'

    def stock_bar(self, obj):
        pct   = min(int((obj.stock / max(obj.stock, 50)) * 100), 100)
        color = '#e84040' if obj.stock == 0 else '#C9A84C' if obj.stock <= 5 else '#22c55e'
        return format_html(
            '<div style="background:#1a1a1a;border-radius:4px;height:6px;width:70px;">'
            '<div style="background:{};height:100%;width:{}%;border-radius:4px;"></div></div>',
            color, pct
        )
    stock_bar.short_description = 'Level'

    def velocity_cell(self, obj):
        _, daily_avg, speed_class, _ = _compute_smart_threshold(obj)
        colors_m = {'fast': '#22c55e', 'med': '#C9A84C', 'slow': '#555'}
        return format_html(
            '<b style="color:{};">{}/day</b>',
            colors_m[speed_class], round(daily_avg, 1)
        )
    velocity_cell.short_description = 'Velocity'

    def stock_status(self, obj):
        threshold, _, _, _ = _compute_smart_threshold(obj)
        if obj.stock == 0:
            return format_html('<b style="color:#e84040;">OUT OF STOCK</b>')
        elif obj.stock <= threshold:
            return format_html('<b style="color:#C9A84C;">LOW (alert ≤{})</b>', threshold)
        return format_html('<b style="color:#22c55e;">OK — {} left</b>', obj.stock)
    stock_status.short_description = 'Status'


@admin.register(Sale)
class SaleAdmin(ImportExportModelAdmin):
    actions      = [generate_pdf_report]
    list_display = ('product', 'quantity', 'revenue_cell', 'timestamp')
    list_filter  = ('timestamp', 'product__category')
    ordering     = ('-timestamp',)

    def revenue_cell(self, obj):
        if obj.product:
            val = float(obj.product.price) * obj.quantity
            return format_html(
                '<b style="color:#22c55e;">₹{}</b>',
                f"{val:,.2f}"
            )
        return '—'
    revenue_cell.short_description = 'Revenue'


@admin.register(Admission)
class AdmissionAdmin(ImportExportModelAdmin):
    list_display  = ('full_name_cell', 'email', 'plan', 'start_date', 'amount_cell', 'payments_link')
    list_filter   = ('plan', 'gender', 'start_date')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    ordering      = ('-created_at',)
    fieldsets = (
        ('Personal',    {'fields': ('first_name', 'last_name', 'email', 'phone', 'gender', 'date_of_birth', 'photo')}),
        ('Membership',  {'fields': ('plan', 'start_date', 'duration_months', 'total_amount')}),
        ('Health',      {'fields': ('fitness_goals', 'medical_conditions')}),
        ('Emergency',   {'fields': ('emergency_contact_name', 'emergency_contact_phone')}),
        ('Terms & UPI', {'fields': ('agreed_terms', 'upi_id', 'address')}),
    )

    def full_name_cell(self, obj):
        return format_html('<b>{} {}</b>', obj.first_name, obj.last_name)
    full_name_cell.short_description = 'Member'

    def amount_cell(self, obj):
        return format_html('<b style="color:#C9A84C;">₹{}</b>', obj.total_amount)
    amount_cell.short_description = 'Amount'

    def payments_link(self, obj):
        return format_html(
            '<a href="/admin/body/admissionpayment/?q={}" '
            'style="background:#C9A84C;color:#000;padding:3px 10px;border-radius:5px;'
            'font-size:10px;font-weight:900;text-decoration:none;">LEDGER</a>',
            obj.id
        )
    payments_link.short_description = ''


@admin.register(AdmissionPayment)
class AdmissionPaymentAdmin(ImportExportModelAdmin):
    actions      = [generate_pdf_report]
    list_display = ('txn_cell', 'admission', 'amount_cell', 'mode_cell', 'status_cell', 'created_at')
    list_filter  = ('status', 'payment_mode', 'created_at')
    search_fields = ('admission__email', 'admission__first_name', 'upi_id')
    ordering     = ('-created_at',)

    def txn_cell(self, obj):
        return format_html(
            '<code style="color:#C9A84C;font-size:10px;">{}</code>',
            str(obj.transaction_id)[:18] + '…'
        )
    txn_cell.short_description = 'Transaction'

    def amount_cell(self, obj):
        return format_html('<b style="color:#22c55e;">₹{}</b>', obj.amount)
    amount_cell.short_description = 'Amount'

    def mode_cell(self, obj):
        return format_html('<span style="color:#3b82f6;font-weight:700;">{}</span>', obj.payment_mode)
    mode_cell.short_description = 'Mode'

    def status_cell(self, obj):
        c = {'success': '#22c55e', 'pending': '#C9A84C', 'failed': '#e84040'}
        return format_html(
            '<b style="color:{};">{}</b>',
            c.get(obj.status, '#aaa'), obj.status.upper()
        )
    status_cell.short_description = 'Status'


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display  = ('name', 'price_month_cell', 'price_annual', 'duration_days', 'is_popular')
    list_editable = ('is_popular',)
    ordering      = ('price_month',)

    def price_month_cell(self, obj):
        return format_html('<b style="color:#C9A84C;">₹{}/mo</b>', obj.price_month)
    price_month_cell.short_description = 'Monthly'


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display  = ('thumb', 'name', 'specialization', 'is_active', 'order')
    list_editable = ('is_active', 'order')
    ordering      = ('order',)

    def thumb(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;">',
                obj.image_url
            )
        return '🏋️'
    thumb.short_description = ''


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'user', 'city', 'state', 'type', 'is_default')
    list_filter   = ('type', 'is_default', 'state')
    search_fields = ('full_name', 'user__email', 'city', 'pincode')


admin.site.register(GalleryImage)