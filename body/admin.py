"""
admin.py — GYM-SHIM Full IMS v4.0
Replace your ENTIRE existing admin.py with this file.
"""

import json
from collections import defaultdict
from datetime import timedelta, date

from django.contrib import admin
from django.utils.html import format_html
from django.http import HttpResponse
from django.db.models import Sum, Count, Q, F, Max
from django.utils import timezone

# PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

try:
    from import_export.admin import ImportExportModelAdmin
except ImportError:
    ImportExportModelAdmin = admin.ModelAdmin

from .models import (
    Admission, MembershipPlan, Trainer, GalleryImage,
    Product, Sale, AdmissionPayment, ProductOrder, UserAddress
)


# ═══════════════════════════════════════════════════════════════
#  CORE DATA ENGINE
# ═══════════════════════════════════════════════════════════════

def _fmt(n):
    """Format number with commas."""
    return f"{float(n):,.0f}"


def _compute_smart_threshold(product):
    """
    Smart dynamic alert threshold based on individual product velocity.
    Fast mover (≥5/day)  → stock for 10 days = alert_at = daily_avg * 10
    Medium mover (1–5/day) → stock for 7 days
    Slow mover (<1/day)  → fixed alert at 3 units
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
    """
    Simple heuristic: take the last meaningful parts of an address
    as city/state. Works for most Indian address formats.
    """
    if not address_text:
        return 'Unknown', 'Unknown'
    parts = [p.strip() for p in address_text.replace('\n', ',').split(',') if p.strip()]
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    elif len(parts) == 1:
        return parts[0], parts[0]
    return 'Unknown', 'Unknown'


def get_dashboard_stats():
    """
    Master function — collects EVERY piece of data the dashboard needs.
    Called once per admin index page load.
    """

    # ── 1. REVENUE ──────────────────────────────────────────────
    sales = Sale.objects.select_related('product').all()
    store_rev = sum(float(s.product.price) * s.quantity for s in sales)

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
    low_stock_cnt = Product.objects.filter(stock__lte=5).count()

    # ── 3. WEEKLY REVENUE (last 7 days) ──────────────────────────
    weekly = []
    for i in range(6, -1, -1):
        day = timezone.now().date() - timedelta(days=i)
        day_sales = Sale.objects.filter(timestamp__date=day).select_related('product')
        daily = sum(float(s.product.price) * s.quantity for s in day_sales)
        weekly.append(round(daily))

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
    products = Product.objects.all()
    inventory_detail = []
    inventory_json_list = []

    for p in products:
        threshold, daily_avg, speed_class, speed_label = _compute_smart_threshold(p)
        is_alert = p.stock <= threshold
        max_stock = 100
        pct = min(int((p.stock / max_stock) * 100), 100)
        bar_color = '#e84040' if p.stock == 0 else '#C9A84C' if is_alert else '#22c55e'

        inventory_detail.append({
            'id': p.id, 'name': p.name, 'category': p.category,
            'stock': p.stock, 'alert_threshold': threshold,
            'is_alert': is_alert, 'pct': pct, 'bar_color': bar_color,
        })
        inventory_json_list.append({
            'name': p.name, 'stock': p.stock,
            'alert_threshold': threshold, 'is_alert': is_alert,
            'category': p.category,
        })

    inventory_json = json.dumps(inventory_json_list)

    # ── 6. VELOCITY — top/slow selling ──────────────────────────
    product_sales = defaultdict(lambda: {'name':'','category':'','units':0,'revenue':0.0,'last_sale':None})
    for s in Sale.objects.select_related('product').all():
        pk = s.product.id
        product_sales[pk]['name']     = s.product.name
        product_sales[pk]['category'] = s.product.category
        product_sales[pk]['units']    += s.quantity
        product_sales[pk]['revenue']  += float(s.product.price) * s.quantity
        if not product_sales[pk]['last_sale'] or s.timestamp > product_sales[pk]['last_sale']:
            product_sales[pk]['last_sale'] = s.timestamp

    # Top selling
    sorted_by_units = sorted(product_sales.items(), key=lambda x: x[1]['units'], reverse=True)
    top_selling = []
    for pk, d in sorted_by_units[:8]:
        _, daily_avg, speed_class, speed_label = _compute_smart_threshold(Product.objects.get(id=pk))
        top_selling.append({
            'name': d['name'], 'category': d['category'],
            'units_sold': d['units'], 'revenue': f"{d['revenue']:,.0f}",
            'speed_class': speed_class, 'speed_label': speed_label,
        })

    # Slow / dead stock
    slow_selling = []
    sold_ids = set(product_sales.keys())
    now = timezone.now()
    for p in products:
        if p.id not in sold_ids:
            slow_selling.append({'name': p.name, 'units_sold': 0, 'stock': p.stock, 'days_since': 999})
        else:
            d = product_sales[p.id]
            if d['units'] < 5:  # low total sales
                last = d['last_sale']
                days = (now - last).days if last else 999
                slow_selling.append({'name': p.name, 'units_sold': d['units'], 'stock': p.stock, 'days_since': days})
    slow_selling.sort(key=lambda x: x['days_since'], reverse=True)
    slow_selling = slow_selling[:6]

    # Velocity items for smart threshold panel
    velocity_items = []
    max_daily = 1.0
    for pk, d in sorted_by_units[:8]:
        _, daily_avg, speed_class, speed_label = _compute_smart_threshold(Product.objects.get(id=pk))
        if daily_avg > max_daily:
            max_daily = daily_avg
        velocity_items.append({'name': d['name'], 'daily_avg': round(daily_avg, 1),
                                'speed_class': speed_class, 'speed_label': speed_label, '_raw': daily_avg})
    for v in velocity_items:
        v['vel_pct'] = min(int((v['_raw'] / max_daily) * 100), 100)

    # ── 7. CUSTOMERS ────────────────────────────────────────────
    email_orders = (
        ProductOrder.objects.values('email', 'full_name')
        .annotate(order_count=Count('id'), total_spent=Sum('total_amount'))
        .order_by('-order_count')
    )
    repeat_customers  = sum(1 for e in email_orders if e['order_count'] > 1)
    one_time_customers = sum(1 for e in email_orders if e['order_count'] == 1)

    top_customers = [
        {
            'name':  e['full_name'],
            'email': e['email'],
            'order_count': e['order_count'],
            'total_spent': f"{float(e['total_spent'] or 0):,.0f}",
        }
        for e in email_orders[:8]
    ]

    # Frequency distribution (how many customers have 1, 2, 3, 4, 5+ orders)
    freq = defaultdict(int)
    for e in email_orders:
        bucket = str(min(e['order_count'], 5))
        freq[bucket] += 1
    freq_labels = ['1','2','3','4','5+']
    freq_data_vals = [freq.get(str(i), 0) for i in range(1,5)] + [freq.get('5',0)]
    freq_data = {'labels': freq_labels, 'data': freq_data_vals}

    # Buyer lifestyle — inferred from product category purchases
    gym = corporate = casual = athlete = 0
    for order in ProductOrder.objects.select_related('product').all():
        cat = order.product.category.lower()
        if 'supplement' in cat:
            gym     += 1
        elif 'apparel' in cat:
            corporate += 1
        elif 'gear' in cat:
            athlete += 1
        else:
            casual  += 1
    lifestyle_data = {
        'labels': ['Gym Goers', 'Corporate', 'Casual', 'Athletes'],
        'data':   [gym, corporate, casual, athlete],
    }

    # Buyer segments
    buyer_segments = [
        {'label': 'Gym Enthusiasts',    'desc': 'Bought Supplements or Gear',     'icon': 'dumbbell',    'color': '#22c55e', 'bg': 'rgba(34,197,94,0.12)',   'count': gym + athlete, 'pct': 0},
        {'label': 'Corporate / Casual', 'desc': 'Bought Apparel or mixed items',  'icon': 'briefcase',   'color': '#3b82f6', 'bg': 'rgba(59,130,246,0.12)',  'count': corporate + casual, 'pct': 0},
        {'label': 'Repeat Buyers',      'desc': 'Placed more than one order',     'icon': 'rotate',      'color': '#C9A84C', 'bg': 'rgba(201,168,76,0.12)', 'count': repeat_customers, 'pct': 0},
        {'label': 'New Customers',      'desc': 'First-time purchase only',       'icon': 'user-plus',   'color': '#a855f7', 'bg': 'rgba(168,85,247,0.12)', 'count': one_time_customers, 'pct': 0},
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
        city_data[city]['orders']  += 1
        city_data[city]['revenue'] += float(order.total_amount)
        city_data[city]['state']    = state
        city_data[city]['products'][order.product.name] += 1

    total_rev_geo = sum(d['revenue'] for d in city_data.values()) or 1
    geo_sorted = sorted(city_data.items(), key=lambda x: x[1]['revenue'], reverse=True)

    geo_data = []
    geo_chart_labels, geo_chart_revs, geo_chart_orders = [], [], []
    for city, d in geo_sorted[:10]:
        pct = round((d['revenue'] / total_rev_geo) * 100)
        top_prod = max(d['products'], key=d['products'].get) if d['products'] else '—'
        geo_data.append({
            'location': city, 'state': d['state'],
            'orders': d['orders'], 'revenue': _fmt(d['revenue']),
            'pct': pct, 'top_product': top_prod,
            'users': d['orders'],  # approx users = unique orders from that city
        })
        geo_chart_labels.append(city)
        geo_chart_revs.append(round(d['revenue']))
        geo_chart_orders.append(d['orders'])

    geo_chart_data = {'labels': geo_chart_labels, 'revenues': geo_chart_revs, 'orders': geo_chart_orders}

    # ── 9. ABC ANALYSIS ─────────────────────────────────────────
    all_products_rev = []
    for p in products:
        rev = sum(float(s.product.price) * s.quantity
                  for s in Sale.objects.filter(product=p).select_related('product'))
        all_products_rev.append((p.name, rev))

    all_products_rev.sort(key=lambda x: x[1], reverse=True)
    grand_total_rev = sum(r for _, r in all_products_rev) or 1

    abc_items      = []
    abc_counts     = {'A': 0, 'B': 0, 'C': 0}
    abc_labels     = []
    abc_revenues   = []
    abc_classes    = []
    cumulative_pct = 0

    for name, rev in all_products_rev:
        pct = round((rev / grand_total_rev) * 100, 1)
        cumulative_pct = min(cumulative_pct + pct, 100)
        cls = 'A' if cumulative_pct <= 70 else 'B' if cumulative_pct <= 90 else 'C'
        abc_counts[cls] += 1
        abc_items.append({
            'name': name, 'revenue': _fmt(rev),
            'pct': pct, 'cumulative': round(cumulative_pct),
            'class': cls,
        })
        abc_labels.append(name[:18] + ('…' if len(name) > 18 else ''))
        abc_revenues.append(round(rev))
        abc_classes.append(cls)

    abc_chart_data = {'labels': abc_labels, 'revenue': abc_revenues, 'classes': abc_classes}

    # ── 10. REVENUE SPLIT rows ───────────────────────────────────
    total_disp = total_rev or 1
    revenue_split = [
        {'label': 'Membership Sales', 'value': _fmt(membership_rev), 'color': '#C9A84C',
         'pct': round((membership_rev / total_disp) * 100)},
        {'label': 'Store / Products',  'value': _fmt(store_rev),      'color': '#22c55e',
         'pct': round((store_rev / total_disp) * 100)},
        {'label': 'Operational Loss',  'value': _fmt(op_loss),         'color': '#e84040',
         'pct': round((op_loss / total_disp) * 100)},
    ]
    donut_data = [round(membership_rev), round(store_rev), round(op_loss)]

    # ── 11. LIVE METRICS PANEL ───────────────────────────────────
    avg_order_val = (store_rev / max(total_orders, 1))
    live_metrics = [
        {'label': 'Avg Order Value',  'sub': 'Store orders',     'value': f"₹{avg_order_val:,.0f}", 'icon': 'cart-shopping', 'color': '#C9A84C', 'bg': 'rgba(201,168,76,0.12)'},
        {'label': 'Products In Stock','sub': 'Currently available','value': str(total_prods - out_of_stock), 'icon': 'box',          'color': '#22c55e', 'bg': 'rgba(34,197,94,0.12)'},
        {'label': 'Out of Stock',     'sub': 'Needs restocking',  'value': str(out_of_stock),        'icon': 'triangle-exclamation', 'color': '#e84040', 'bg': 'rgba(232,64,64,0.12)'},
        {'label': 'Low Stock Alerts', 'sub': 'Smart threshold',   'value': str(low_stock_cnt),       'icon': 'bell',         'color': '#fb923c', 'bg': 'rgba(251,146,60,0.12)'},
    ]

    # ── 12. RECENT ACTIVITY ──────────────────────────────────────
    recent_orders   = ProductOrder.objects.select_related('product').order_by('-created_at')[:7]
    recent_payments = AdmissionPayment.objects.select_related('admission').order_by('-created_at')[:4]

    # ── RETURN ALL ───────────────────────────────────────────────
    return {
        # KPIs
        'total_revenue':    _fmt(total_rev),
        'net_profit':       _fmt(net_profit),
        'operational_loss': _fmt(op_loss),
        'membership_revenue': _fmt(membership_rev),
        'store_revenue':    _fmt(store_rev),
        'total_members':    total_members,
        'total_orders':     total_orders,
        'total_products':   total_prods,
        'out_of_stock':     out_of_stock,
        'low_stock_count':  f"{low_stock_cnt:02d}",

        # Raw for JS sparklines
        'total_revenue_raw':    round(total_rev),
        'net_profit_raw':       round(net_profit),
        'op_loss_raw':          round(op_loss),
        'membership_revenue_raw': round(membership_rev),
        'store_revenue_raw':    round(store_rev),

        # Charts
        'weekly_revenue':   json.dumps(weekly),
        'donut_data':       json.dumps(donut_data),
        'revenue_split':    revenue_split,
        'geo_chart_data':   json.dumps(geo_chart_data),
        'abc_chart_data':   json.dumps(abc_chart_data),
        'freq_data':        json.dumps(freq_data),
        'lifestyle_data':   json.dumps(lifestyle_data),

        # Panels
        'order_pipeline':   order_pipeline,
        'inventory_detail': inventory_detail,
        'inventory_json':   inventory_json,
        'velocity_items':   velocity_items,
        'top_selling':      top_selling,
        'slow_selling':     slow_selling,

        # Customers
        'repeat_customers':    repeat_customers,
        'one_time_customers':  one_time_customers,
        'top_customers':       top_customers,
        'buyer_segments':      buyer_segments,

        # Geography
        'geo_data':         geo_data,

        # ABC
        'abc_items':        abc_items,
        'abc_counts':       abc_counts,

        # Misc
        'live_metrics':     live_metrics,
        'recent_orders':    recent_orders,
        'recent_payments':  recent_payments,
    }


# ── Hook into Django admin index ──
original_index = admin.site.__class__.index

def custom_index(self, request, extra_context=None):
    extra_context = extra_context or {}
    try:
        extra_context.update(get_dashboard_stats())
    except Exception as e:
        extra_context['dashboard_error'] = str(e)
    return original_index(self, request, extra_context)

admin.site.__class__.index = custom_index
admin.site.index_template   = 'admin/index.html'  # your template name


# ═══════════════════════════════════════════════════════════════
#  PDF EXPORT ACTION (shared)
# ═══════════════════════════════════════════════════════════════

def generate_pdf_report(modeladmin, request, queryset):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="GymShim_Report.pdf"'
    doc  = SimpleDocTemplate(response, pagesize=letter)
    styl = getSampleStyleSheet()
    elms = [Paragraph("GYM-SHIM · OFFICIAL BUSINESS REPORT", styl['Title']), Spacer(1, 16)]

    model_name = queryset.model.__name__
    if model_name in ['Sale', 'ProductOrder', 'AdmissionPayment']:
        data  = [["ID", "Item / Member", "Amount (₹)", "Date"]]
        total = 0.0
        for obj in queryset:
            amt  = getattr(obj, 'total_amount', None) or getattr(obj, 'amount', None)
            if amt is None and hasattr(obj, 'product'):
                amt = obj.product.price * getattr(obj, 'quantity', 1)
            amt   = float(amt or 0); total += amt
            name  = obj.product.name if hasattr(obj, 'product') else str(obj)
            date_ = obj.timestamp.strftime('%d/%m/%Y') if hasattr(obj, 'timestamp') else \
                    obj.created_at.strftime('%d/%m/%Y') if hasattr(obj, 'created_at') else '—'
            data.append([str(obj.id), name, f"{amt:,.2f}", date_])
        data.append(["", "GRAND TOTAL", f"{total:,.2f}", ""])
    else:
        data = [["ID", "Record"]]
        for obj in queryset:
            data.append([str(obj.id), str(obj)])

    tbl = Table(data, colWidths=[45, 255, 110, 85])
    tbl.setStyle(TableStyle([
        ('BACKGROUND', (0,0),  (-1,0),  colors.HexColor('#C9A84C')),
        ('TEXTCOLOR',  (0,0),  (-1,0),  colors.black),
        ('FONTNAME',   (0,0),  (-1,0),  'Helvetica-Bold'),
        ('FONTSIZE',   (0,0),  (-1,-1), 9),
        ('ALIGN',      (0,0),  (-1,-1), 'CENTER'),
        ('ROWBACKGROUNDS', (0,1), (-1,-2), [colors.HexColor('#f9f9f9'), colors.white]),
        ('GRID',       (0,0),  (-1,-1), 0.5, colors.HexColor('#cccccc')),
        ('FONTNAME',   (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#f0ede6')),
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
    actions       = [generate_pdf_report]
    list_display  = ('order_badge', 'full_name', 'product_link', 'amount_cell', 'status_badge', 'created_at')
    list_filter   = ('status', 'created_at', 'product__category')
    search_fields = ('full_name', 'email', 'phone', 'transaction_id')
    ordering      = ('-created_at',)
    readonly_fields = ('transaction_id', 'created_at')
    fieldsets = (
        ('Order',    {'fields': ('product', 'status', 'total_amount', 'transaction_id')}),
        ('Customer', {'fields': ('full_name', 'email', 'phone', 'address')}),
        ('Payment',  {'fields': ('upi_ref',)}),
        ('Meta',     {'fields': ('created_at',)}),
    )

    def order_badge(self, obj):
        return format_html('<b style="color:#C9A84C;font-family:monospace;">#{}</b>', obj.id)
    order_badge.short_description = 'Order'

    def product_link(self, obj):
        return format_html('<a href="/admin/body/product/{}/change/" style="color:#3b82f6;">{}</a>', obj.product.id, obj.product.name)
    product_link.short_description = 'Product'

    def amount_cell(self, obj):
        return format_html('<b style="color:#22c55e;">₹{}</b>', obj.total_amount)
    amount_cell.short_description = 'Amount'

    def status_badge(self, obj):
        p = {'pending':('#C9A84C','#000'),'paid':('#22c55e','#000'),'shipped':('#3b82f6','#fff'),'delivered':('#10b981','#fff'),'cancelled':('#e84040','#fff')}
        bg, fg = p.get(obj.status, ('#333','#fff'))
        return format_html('<span style="background:{};color:{};padding:3px 12px;border-radius:20px;font-weight:900;font-size:10px;">{}</span>', bg, fg, obj.status.upper())
    status_badge.short_description = 'Status'


@admin.register(Product)
class ProductAdmin(ImportExportModelAdmin):
    list_display  = ('thumb', 'name', 'category', 'price_cell', 'stock_bar', 'velocity_cell', 'stock_status')
    list_filter   = ('category',)
    search_fields = ('name', 'description')
    ordering      = ('stock',)
    fieldsets = (
        ('Product',         {'fields': ('name', 'category', 'description', 'image_url')}),
        ('Pricing & Stock', {'fields': ('price', 'stock')}),
    )

    def thumb(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="width:36px;height:36px;border-radius:7px;object-fit:cover;">', obj.image_url)
        return '📦'
    thumb.short_description = ''

    def price_cell(self, obj):
        return format_html('<b style="color:#C9A84C;">₹{}</b>', obj.price)
    price_cell.short_description = 'Price'

    def stock_bar(self, obj):
        pct   = min(int((obj.stock / 50) * 100), 100)
        color = '#e84040' if obj.stock == 0 else '#C9A84C' if obj.stock <= 5 else '#22c55e'
        return format_html('<div style="background:#222;border-radius:4px;height:6px;width:70px;"><div style="background:{};height:100%;width:{}%;border-radius:4px;"></div></div>', color, pct)
    stock_bar.short_description = 'Level'

    def velocity_cell(self, obj):
        _, daily_avg, speed_class, speed_label = _compute_smart_threshold(obj)
        colors_map = {'fast': '#22c55e', 'med': '#C9A84C', 'slow': '#555'}
        return format_html('<b style="color:{};">{}/day</b>', colors_map[speed_class], round(daily_avg, 1))
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
    actions = [generate_pdf_report]
    list_display = ('product', 'quantity', 'revenue_cell', 'timestamp')
    list_filter = ('timestamp', 'product__category')
    ordering = ('-timestamp',)

    def revenue_cell(self, obj):
        revenue = float(obj.product.price) * obj.quantity
        return format_html(
            '<b style="color:#22c55e;">₹{}</b>',
            f"{revenue:,.2f}"
        )

    revenue_cell.short_description = 'Revenue'


@admin.register(Admission)
class AdmissionAdmin(ImportExportModelAdmin):
    list_display  = ('full_name_cell', 'email', 'plan', 'start_date', 'amount_cell', 'payments_link')
    list_filter   = ('plan', 'gender', 'start_date')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
    ordering      = ('-created_at',)
    fieldsets = (
        ('Personal',    {'fields': ('first_name','last_name','email','phone','gender','date_of_birth','photo')}),
        ('Membership',  {'fields': ('plan','start_date','duration_months','total_amount')}),
        ('Health',      {'fields': ('fitness_goals','medical_conditions')}),
        ('Emergency',   {'fields': ('emergency_contact_name','emergency_contact_phone')}),
        ('Terms & UPI', {'fields': ('agreed_terms','upi_id','address')}),
    )

    def full_name_cell(self, obj):
        return format_html('<b>{} {}</b>', obj.first_name, obj.last_name)
    full_name_cell.short_description = 'Member'

    def amount_cell(self, obj):
        return format_html('<b style="color:#C9A84C;">₹{}</b>', obj.total_amount)
    amount_cell.short_description = 'Amount'

    def payments_link(self, obj):
        return format_html('<a href="/admin/body/admissionpayment/?q={}" style="background:#C9A84C;color:#000;padding:3px 10px;border-radius:5px;font-size:10px;font-weight:900;text-decoration:none;">LEDGER</a>', obj.id)
    payments_link.short_description = ''


@admin.register(AdmissionPayment)
class AdmissionPaymentAdmin(ImportExportModelAdmin):
    actions      = [generate_pdf_report]
    list_display = ('txn_cell', 'admission', 'amount_cell', 'mode_cell', 'status_cell', 'created_at')
    list_filter  = ('status', 'payment_mode', 'created_at')
    search_fields = ('admission__email', 'admission__first_name', 'upi_id')
    ordering     = ('-created_at',)

    def txn_cell(self, obj):
        return format_html('<code style="color:#C9A84C;font-size:10px;">{}</code>', str(obj.transaction_id)[:16]+'…')
    txn_cell.short_description = 'Transaction ID'

    def amount_cell(self, obj):
        return format_html('<b style="color:#22c55e;">₹{}</b>', obj.amount)
    amount_cell.short_description = 'Amount'

    def mode_cell(self, obj):
        return format_html('<span style="color:#3b82f6;font-weight:700;">{}</span>', obj.payment_mode)
    mode_cell.short_description = 'Mode'

    def status_cell(self, obj):
        c = {'success':'#22c55e','pending':'#C9A84C','failed':'#e84040'}
        return format_html('<b style="color:{};">{}</b>', c.get(obj.status,'#aaa'), obj.status.upper())
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
            return format_html('<img src="{}" style="width:34px;height:34px;border-radius:50%;object-fit:cover;">', obj.image_url)
        return '🏋️'
    thumb.short_description = ''


@admin.register(UserAddress)
class UserAddressAdmin(admin.ModelAdmin):
    list_display  = ('full_name', 'user', 'city', 'state', 'type', 'is_default')
    list_filter   = ('type', 'is_default', 'state')
    search_fields = ('full_name', 'user__email', 'city', 'pincode')


admin.site.register(GalleryImage)