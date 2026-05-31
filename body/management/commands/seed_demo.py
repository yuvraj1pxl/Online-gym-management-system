import random
from decimal import Decimal
from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User

from body.models import (
    MembershipPlan, Admission, AdmissionPayment, 
    Product, Sale, ProductOrder, UserAddress
)

class Command(BaseCommand):
    help = 'Clears existing IMS/admission records and seeds realistic, defensible 60-day business demo data.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Starting demo database seeding execution..."))

        now = timezone.now()

        # 1. Base Pools
        products_data = [
            {"name": "Whey Protein Isolate 2kg", "description": "Premium ultra-filtered grass-fed whey protein isolate.", "price": Decimal("5499.00"), "stock": 45, "category": "Supplements", "weight": 8},
            {"name": "Micronized Creatine 250g", "description": "100% pure monohydrate for power and endurance.", "price": Decimal("999.00"), "stock": 60, "category": "Supplements", "weight": 10},
            {"name": "Explosive Pre-Workout 300g", "description": "High stim focus and pump matrix.", "price": Decimal("1899.00"), "stock": 20, "category": "Supplements", "weight": 7},
            {"name": "Essential BCAA Hydration", "description": "Branched-chain amino acids with electrolytes.", "price": Decimal("1299.00"), "stock": 15, "category": "Supplements", "weight": 5},
            {"name": "Daily Multi-Vitamin 60 tabs", "description": "Complete micronutrient profile for athletes.", "price": Decimal("699.00"), "stock": 10, "category": "Supplements", "weight": 4},
            {"name": "Pro Lifting Leather Belt", "description": "4-inch wide premium cowhide leather support.", "price": Decimal("2499.00"), "stock": 12, "category": "Gear", "weight": 3},
            {"name": "Heavy Duty Wrist Wraps (Pair)", "description": "Maximum support for bench and shoulder press.", "price": Decimal("499.00"), "stock": 35, "category": "Gear", "weight": 9},
            {"name": "7mm Neoprene Knee Sleeves", "description": "Joint warmth and compression for squats.", "price": Decimal("1499.00"), "stock": 8, "category": "Gear", "weight": 5},
            {"name": "Smart Shaker Bottle 700ml", "description": "Leak-proof with protein compartment.", "price": Decimal("349.00"), "stock": 80, "category": "Gear", "weight": 10},
            {"name": "Tactical Gym Duffel Bag", "description": "Waterproof multi-pocket gear storage.", "price": Decimal("1999.00"), "stock": 5, "category": "Gear", "weight": 2},
            {"name": "SHIM Performance Hoodie", "description": "Warm, breathable cotton-fleece blend.", "price": Decimal("1599.00"), "stock": 15, "category": "Apparel", "weight": 4},
            {"name": "Vintage Muscle Stringer Tank", "description": "Deep-cut cotton tank for physique display.", "price": Decimal("599.00"), "stock": 22, "category": "Apparel", "weight": 8},
            {"name": "Elite Compression Shorts", "description": "Double layer shorts with phone pocket.", "price": Decimal("899.00"), "stock": 18, "category": "Apparel", "weight": 5},
            {"name": "Premium Cotton Lifting Straps", "description": "Heavy-duty canvas straps for deadlifts.", "price": Decimal("399.00"), "stock": 3, "category": "Gear", "weight": 8},
            {"name": "Extreme Mass Gainer 3kg", "description": "High calorie mass gainer for hardgainers.", "price": Decimal("3999.00"), "stock": 30, "category": "Supplements", "weight": 6},
            {"name": "Glutamine Recovery Powder", "description": "100% pure L-Glutamine for muscle recovery.", "price": Decimal("899.00"), "stock": 40, "category": "Supplements", "weight": 5},
            {"name": "Hydrolyzed Collagen Peptides", "description": "Premium joint, skin, and hair support.", "price": Decimal("1999.00"), "stock": 25, "category": "Supplements", "weight": 4},
            {"name": "Vegan Pea & Rice Protein", "description": "Plant-based gluten-free protein powder.", "price": Decimal("2999.00"), "stock": 20, "category": "Supplements", "weight": 4},
            {"name": "ZMA Zinc & Magnesium Complex", "description": "Optimizes sleep quality and recovery.", "price": Decimal("749.00"), "stock": 50, "category": "Supplements", "weight": 5},
            {"name": "Premium Liquid Chalk 250ml", "description": "No-mess liquid chalk for ultimate grip.", "price": Decimal("449.00"), "stock": 60, "category": "Gear", "weight": 7},
            {"name": "High-Density Foam Roller", "description": "For deep tissue muscle massage.", "price": Decimal("799.00"), "stock": 35, "category": "Gear", "weight": 5},
            {"name": "Adjustable Steel Jump Rope", "description": "Speed rope with ball bearings.", "price": Decimal("499.00"), "stock": 80, "category": "Gear", "weight": 8},
            {"name": "Latex Resistance Bands Set", "description": "Five levels of resistance loop bands.", "price": Decimal("699.00"), "stock": 45, "category": "Gear", "weight": 7},
            {"name": "Heavy-Duty Ab Wheel", "description": "Double-wheeled core training machine.", "price": Decimal("599.00"), "stock": 30, "category": "Gear", "weight": 6},
            {"name": "Performance Crew Socks (3-pack)", "description": "Cushioned sweat-wicking sport socks.", "price": Decimal("399.00"), "stock": 100, "category": "Apparel", "weight": 8},
            {"name": "Quick-Dry Active Training Tee", "description": "Lightweight breathable gym shirt.", "price": Decimal("799.00"), "stock": 60, "category": "Apparel", "weight": 8},
            {"name": "Oversized 'SHIM' Heavy Tee", "description": "Heavyweight cotton drop-shoulder streetwear.", "price": Decimal("999.00"), "stock": 50, "category": "Apparel", "weight": 9},
            {"name": "Elite Athletic Track Pants", "description": "Tapered training joggers with zipper pockets.", "price": Decimal("1499.00"), "stock": 35, "category": "Apparel", "weight": 6},
        ]

        customers = [
            # VIPs / Repeat Customers (mostly Ranchi addresses mapped to key neighborhoods)
            {"name": "Amit Sharma", "email": "amit.sharma@gmail.com", "phone": "9876543210", "address": "HB Road, Lalpur, Jharkhand, 834001", "is_vip": True},
            {"name": "Priyanka Verma", "email": "priyanka.verma@yahoo.com", "phone": "8765432109", "address": "Ranchi Centro Mall, Ranchi Centro, Jharkhand, 834001", "is_vip": True},
            {"name": "Rajesh Kumar", "email": "rajesh.kumar@outlook.com", "phone": "7654321098", "address": "Near Kanke Block, Kanke, Jharkhand, 834008", "is_vip": True},
            {"name": "Sneha Sen", "email": "sneha.sen@gmail.com", "phone": "9988776655", "address": "High Court Area, Doranda, Jharkhand, 834002", "is_vip": True},
            
            # Other Cities / regular buyers
            {"name": "Rahul Gupta", "email": "rahul.gupta@gmail.com", "phone": "9123456789", "address": "Boring Road, Patna, Bihar, 800001", "is_vip": False},
            {"name": "Ananya Roy", "email": "ananya.roy@gmail.com", "phone": "9234567890", "address": "Salt Lake Sector 5, Kolkata, West Bengal, 700091", "is_vip": False},
            {"name": "Vikram Malhotra", "email": "vikram.m@gmail.com", "phone": "9345678901", "address": "Link Road, Mumbai, Maharashtra, 400053", "is_vip": False},
            {"name": "Divya Rao", "email": "divya.rao@hotmail.com", "phone": "9456789012", "address": "100 Feet Road, Bangalore, Karnataka, 560038", "is_vip": False},
            {"name": "Siddharth Singh", "email": "sid.singh@gmail.com", "phone": "9567890123", "address": "Connaught Place, New Delhi, Delhi, 110001", "is_vip": False},
            {"name": "Nisha Dubey", "email": "nisha.dubey@gmail.com", "phone": "9678901234", "address": "Ranchi Centro Mall, Ranchi Centro, Jharkhand, 834001", "is_vip": False},
            {"name": "Aditya Prasad", "email": "aditya.p@gmail.com", "phone": "9789012345", "address": "HB Road, Lalpur, Jharkhand, 834001", "is_vip": False},
            {"name": "Meera Nair", "email": "meera.nair@gmail.com", "phone": "9890123456", "address": "Near Kanke Block, Kanke, Jharkhand, 834008", "is_vip": False},
        ]

        # 2. Cleanup existing records
        self.stdout.write(self.style.WARNING("Cleaning database transactions..."))
        Sale.objects.all().delete()
        ProductOrder.objects.all().delete()
        AdmissionPayment.objects.all().delete()
        Admission.objects.all().delete()
        Product.objects.all().delete()

        # Re-fetch or create MembershipPlans
        plans = list(MembershipPlan.objects.all())
        if not plans:
            plans = [
                MembershipPlan.objects.get_or_create(name="Basic", defaults={"price_month": 999, "price_annual": 9590})[0],
                MembershipPlan.objects.get_or_create(name="Premium", defaults={"price_month": 1999, "price_annual": 19180})[0],
                MembershipPlan.objects.get_or_create(name="Elite", defaults={"price_month": 2999, "price_annual": 28770})[0],
            ]

        # 3. Synchronize Users and Addresses
        self.stdout.write("Syncing demo users and addresses...")
        for c in customers:
            user, created = User.objects.get_or_create(
                username=c['email'],
                defaults={
                    'email': c['email'],
                    'first_name': c['name'].split()[0],
                    'last_name': c['name'].split()[1] if len(c['name'].split()) > 1 else ''
                }
            )
            if created:
                user.set_password('demo1234')
                user.save()
            
            # Setup default UserAddress
            addr_parts = [p.strip() for p in c['address'].split(',')]
            UserAddress.objects.get_or_create(
                user=user,
                full_name=c['name'],
                phone=c['phone'],
                defaults={
                    'line1': addr_parts[0],
                    'city': addr_parts[1],
                    'state': addr_parts[2],
                    'pincode': addr_parts[3],
                    'is_default': True
                }
            )

        # 4. Generate data structures in memory to handle stock mathematical projection
        self.stdout.write("Simulating transactions over a 60-day horizon...")
        admission_records = []
        order_records = []

        product_names = [p["name"] for p in products_data]
        product_weights = [p["weight"] for p in products_data]
        product_sales_count = {name: 0 for name in product_names}

        # Admissions Simulation
        num_admissions = random.randint(40, 60)
        for _ in range(num_admissions):
            customer = random.choice(customers)
            plan = random.choice(plans)
            
            days_ago = random.randint(0, 60)
            txn_date = now - timedelta(days=days_ago)
            txn_time = time(random.randint(6, 21), random.randint(0, 59), random.randint(0, 59))
            txn_datetime = timezone.make_aware(datetime.combine(txn_date.date(), txn_time))
            
            duration_months = random.choice([1, 3, 6, 12])
            total_amount = plan.price_month * duration_months
            status = random.choices(['success', 'pending', 'failed'], weights=[85, 10, 5])[0]

            admission_records.append({
                'customer': customer,
                'plan': plan,
                'datetime': txn_datetime,
                'duration_months': duration_months,
                'total_amount': total_amount,
                'status': status
            })

        # Product Orders & Sales Simulation
        num_orders = random.randint(85, 110)
        vip_customers = [c for c in customers if c['is_vip']]
        regular_customers = [c for c in customers if not c['is_vip']]

        for _ in range(num_orders):
            # VIPs have a higher repeat purchase frequency
            if random.random() < 0.60:
                customer = random.choice(vip_customers)
            else:
                customer = random.choice(regular_customers)

            prod_name = random.choices(product_names, weights=product_weights)[0]

            days_ago = random.randint(0, 60)
            txn_date = now - timedelta(days=days_ago)
            txn_time = time(random.randint(8, 20), random.randint(0, 59), random.randint(0, 59))
            txn_datetime = timezone.make_aware(datetime.combine(txn_date.date(), txn_time))

            status = random.choices(['delivered', 'shipped', 'paid', 'pending', 'cancelled'], weights=[60, 15, 10, 10, 5])[0]
            is_sale = status in ['paid', 'shipped', 'delivered']

            if is_sale:
                product_sales_count[prod_name] += 1

            order_records.append({
                'customer': customer,
                'product_name': prod_name,
                'datetime': txn_datetime,
                'status': status,
                'is_sale': is_sale
            })

        # 5. Create products with mathematically offset stock values
        self.stdout.write("Populating Products table...")
        created_products = {}
        for p in products_data:
            name = p["name"]
            base_stock = p["stock"]
            sales_count = product_sales_count[name]
            initial_stock = base_stock + sales_count

            prod = Product.objects.create(
                name=name,
                description=p["description"],
                price=p["price"],
                stock=initial_stock,
                category=p["category"],
                image_url=f"https://api.dicebear.com/7.x/identicon/svg?seed={name.replace(' ', '')}"
            )
            created_products[name] = prod

        # 6. Commit Admissions
        self.stdout.write("Inserting Admission records...")
        for r in admission_records:
            cust = r['customer']
            adm = Admission.objects.create(
                first_name=cust['name'].split()[0],
                last_name=cust['name'].split()[1] if len(cust['name'].split()) > 1 else '',
                email=cust['email'],
                phone=cust['phone'],
                address=cust['address'],
                plan=r['plan'],
                start_date=r['datetime'].date(),
                duration_months=r['duration_months'],
                total_amount=r['total_amount'],
                upi_id=f"ref-{random.randint(100000, 999999)}@okaxis" if r['status'] == 'success' else '',
                agreed_terms=True
            )
            Admission.objects.filter(id=adm.id).update(created_at=r['datetime'])

            AdmissionPayment.objects.create(
                admission=adm,
                amount=r['total_amount'],
                upi_id=f"{random.randint(100000000000, 999999999999)}" if r['status'] == 'success' else '',
                status=r['status'],
                payment_mode='UPI',
                created_at=r['datetime']
            )

        # 7. Commit Orders & Sales
        self.stdout.write("Inserting ProductOrder and Sale records...")
        for r in order_records:
            cust = r['customer']
            prod = created_products[r['product_name']]

            order = ProductOrder.objects.create(
                product=prod,
                full_name=cust['name'],
                email=cust['email'],
                phone=cust['phone'],
                address=cust['address'],
                total_amount=prod.price,
                upi_ref=f"{random.randint(100000000000, 999999999999)}" if r['is_sale'] else '',
                status=r['status']
            )
            ProductOrder.objects.filter(id=order.id).update(created_at=r['datetime'])

            if r['is_sale']:
                sale = Sale.objects.create(
                    product=prod,
                    quantity=1
                )
                Sale.objects.filter(id=sale.id).update(timestamp=r['datetime'])

        self.stdout.write(self.style.SUCCESS("[OK] Database Seeding Completed Successfully! All charts configured with defensible live data."))
