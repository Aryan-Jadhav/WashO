"""python manage.py seed_demo [--reset]

Loads realistic Pune demo data: staff and delivery agents for the 3 stores, 20 customers
with addresses, and 60 orders spread over the last 6 weeks in EVERY status.

WHY orders are made through the real services (create_order, confirm_pickup, add_garment,
finish_tagging, confirm_delivery ...): the demo data then obeys every business rule and
the PostgreSQL trigger writes the status history exactly as in real use. Afterwards the
timestamps are moved back in time so the dashboard has six weeks of history to show.

The stores, price list, time slots and coupons already come from migrations.
Safe to run again: it skips if demo data exists (use --reset to rebuild it).
"""
import datetime
import random
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.test.utils import override_settings
from django.utils import timezone

from accounts.models import Address, User
from accounts.roles import Role
from catalog.models import ServicePrice
from delivery.services import (assign_delivery_agent, assign_pickup_agent, confirm_delivery, confirm_pickup,
                               start_delivery)
from orders.models import DailySlot, Order, OrderStatusHistory, TimeSlot
from orders.services import BookingError, cancel_order, change_status, create_order
from payments.models import Payment
from stores.models import Store
from tagging.models import CountCheck, Garment, MismatchAlert
from tagging.services import add_garment, finish_tagging, record_count, resolve_alert

S = Order.Status
DEMO_PASSWORD = "Demo@1234"  # documented in README (demo logins); local demo only

# Phone ranges reserved for demo users, so --reset deletes only demo data.
CUSTOMER_PHONE = "90110000{:02d}"
STAFF_PHONE = "90220000{:02d}"
AGENT_PHONE = "90330000{:02d}"
ADMIN_PHONE = "9044000001"
DEMO_PHONE_PREFIXES = ("901100", "902200", "903300", "904400")

TEAM = {  # store slug -> (staff, [agents])
    "washo-kothrud": (("Sunita", "Kale"), [("Ravi", "Shinde"), ("Amol", "Pawar")]),
    "washo-baner": (("Prakash", "Jadhav"), [("Sachin", "More"), ("Vikas", "Gaikwad")]),
    "washo-viman-nagar": (("Meena", "Deshpande"), [("Rahul", "Bhosale"), ("Kiran", "Salunkhe")]),
}

CUSTOMERS = [
    ("Asha", "Patil"), ("Rohan", "Kulkarni"), ("Sneha", "Joshi"), ("Aditya", "Deshmukh"), ("Pooja", "Shinde"),
    ("Nikhil", "Gokhale"), ("Priya", "Bhide"), ("Omkar", "Chavan"), ("Neha", "Apte"), ("Siddharth", "Ranade"),
    ("Kavya", "Phadke"), ("Tejas", "Karve"), ("Ananya", "Sathe"), ("Varun", "Mehta"), ("Isha", "Nair"),
    ("Yash", "Agarwal"), ("Shruti", "Kelkar"), ("Akash", "Wagh"), ("Rutuja", "Mane"), ("Harsh", "Iyer"),
]
BUILDINGS = ["Shanti Niwas", "Sai Heights", "Om Residency", "Ganga Apartments", "Lotus Court", "Shree Krupa",
             "Green Valley", "Sukh Sagar", "Mayur Park", "Siddhivinayak Towers", "Rose Garden", "Kalpataru Avenue"]
LANDMARKS = ["Near D-Mart", "Opp. HDFC Bank", "Behind City Pride", "Near Bus Stop", "Lane 3", "", "", "Near Ganesh Temple"]
STAINS = ["Tea stain on collar", "Ink mark on pocket", "Oil spot on sleeve", "Turmeric stain near hem",
          "Faded patch on back", "Mud on cuffs"]
DAMAGE = ["Button missing", "Small tear near seam", "Zip loose"]

# Popular (service slug, item) pairs with weights, so baskets look realistic.
POPULAR = [
    (("wash-iron", "Shirt"), 10), (("wash-iron", "Trousers"), 7), (("wash-fold", "T-Shirt"), 8),
    (("wash-fold", "Jeans"), 5), (("wash-fold", "Bedsheet (Double)"), 4), (("wash-fold", "Towel"), 4),
    (("wash-iron", "Kurta"), 4), (("laundry", "Shirt"), 3), (("dry-clean", "Saree (Silk)"), 4),
    (("dry-clean", "Blazer / Coat"), 3), (("dry-clean", "Suit (2 piece)"), 2), (("dry-clean", "Sweater"), 2),
    (("dry-clean", "Lehenga (3 piece)"), 1), (("shoe-cleaning", "Sports Shoes"), 2),
    (("home-textiles", "Curtain (per panel)"), 2), (("home-textiles", "Blanket (Double)"), 2),
]

# 60 orders: (final status, days ago the pickup was, how many) - 0 = today, negative = future.
PLAN = (
    [(S.DELIVERED, d, 1) for d in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 21, 23, 24,
                                    25, 26, 28, 30, 32, 34, 36, 38, 40, 42)]
    + [(S.CANCELLED, d, 1) for d in (2, 6, 11, 19, 27)]
    + [(S.BOOKED, d, 1) for d in (-1, -1, -2, -3)]
    + [(S.PICKUP_ASSIGNED, d, 1) for d in (0, 0, -1, -1)]
    + [(S.PICKED_UP, 0, 3)]
    + [(S.AT_STORE, d, 1) for d in (0, 1, 1)]
    + [(S.TAGGED, 1, 2)]
    + [(S.IN_CLEANING, d, 1) for d in (1, 1, 2)]
    + [(S.READY, 2, 3)]
    + [(S.OUT_FOR_DELIVERY, d, 1) for d in (2, 3, 3)]
)
FLOW_RANK = {s: i for i, s in enumerate([S.BOOKED, S.PICKUP_ASSIGNED, S.PICKED_UP, S.AT_STORE, S.TAGGED,
                                          S.IN_CLEANING, S.READY, S.OUT_FOR_DELIVERY, S.DELIVERED])}
# Hours after the pickup-slot start at which each step happened (normal / express).
STEP_HOURS = {S.PICKED_UP: (0.5, 0.5), S.AT_STORE: (2.5, 2), S.TAGGED: (4, 3), S.IN_CLEANING: (5, 3.5),
              S.READY: (27, 12), S.OUT_FOR_DELIVERY: (45, 20), S.DELIVERED: (47, 22)}


def demo_users():
    q = User.objects.none()
    for prefix in DEMO_PHONE_PREFIXES:
        q = q | User.objects.filter(phone__startswith=prefix)
    return q


class Command(BaseCommand):
    help = "Load realistic Pune demo data (staff, agents, 20 customers, 60 orders in every status)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data and load it again.")

    def handle(self, *args, **opts):
        if opts["reset"]:
            self.reset()
        elif demo_users().exists():
            self.stdout.write(self.style.WARNING("Demo data is already loaded - nothing to do. "
                                                 "(Use --reset to delete and rebuild it.)"))
            return
        self.rng = random.Random(2026)  # fixed seed: the same demo data on every computer
        self.now = timezone.now()
        self.today = timezone.localdate()
        # Emails would be sent for ~300 status changes; switch them off while seeding.
        with override_settings(EMAIL_BACKEND="django.core.mail.backends.dummy.EmailBackend"), transaction.atomic():
            self.make_people()
            made = self.make_orders()
        self.report(made)

    # ------------------------------------------------------------------ reset ----
    def reset(self):
        users = demo_users()
        orders = Order.objects.filter(customer__in=users)
        with transaction.atomic():
            for o in orders.exclude(status=S.CANCELLED).select_related("pickup_slot"):
                DailySlot.objects.filter(pk=o.pickup_slot_id, booked_count__gt=0) \
                    .update(booked_count=F("booked_count") - 1)
            Payment.objects.filter(order__in=orders).delete()
            Garment.objects.filter(order__in=orders).delete()
            n = orders.count()
            orders.delete()  # items, history, counts and alerts go with them (CASCADE)
            Address.objects.filter(user__in=users).delete()
            u = users.count()
            users.delete()
        self.stdout.write(f"Removed old demo data: {n} orders, {u} users.")

    # ----------------------------------------------------------------- people ----
    def _user(self, phone, first, last, role, store=None, email=True):
        u = User.objects.create_user(phone, DEMO_PASSWORD, first_name=first, last_name=last, store=store,
                                     email=f"{first}.{last}@example.com".lower() if email else "")
        u.groups.add(Group.objects.get(name=role))
        return u

    def make_people(self):
        self.stores = list(Store.objects.filter(slug__in=TEAM).order_by("name"))
        self.staff, self.agents = {}, {}
        n_staff = n_agent = 0
        for store in self.stores:
            (sf, sl), agents = TEAM[store.slug]
            n_staff += 1
            self.staff[store.pk] = self._user(STAFF_PHONE.format(n_staff), sf, sl, Role.STAFF, store)
            self.agents[store.pk] = []
            for af, al in agents:
                n_agent += 1
                self.agents[store.pk].append(self._user(AGENT_PHONE.format(n_agent), af, al, Role.AGENT, store))
        admin = self._user(ADMIN_PHONE, "Demo", "Admin", Role.ADMIN)
        admin.is_staff = admin.is_superuser = True  # can also open the Django admin site
        admin.save()
        self.admin = admin

        self.customers = []
        for i, (first, last) in enumerate(CUSTOMERS, 1):
            store = self.stores[(i - 1) % len(self.stores)]
            c = self._user(CUSTOMER_PHONE.format(i), first, last, Role.CUSTOMER, email=(i % 4 != 0))
            area = self.rng.choice(list(store.areas.filter(is_active=True)))
            Address.objects.create(
                user=c, label="home", is_default=True, area=area,
                line1=f"Flat {self.rng.randint(1, 12)}0{self.rng.randint(1, 4)}, {self.rng.choice(BUILDINGS)}",
                line2=self.rng.choice(LANDMARKS),
            )
            self.customers.append(c)

    # ----------------------------------------------------------------- orders ----
    def _basket(self):
        pairs, weights = zip(*POPULAR)
        picks, size = set(), self.rng.randint(1, 4)
        while len(picks) < size:
            picks.add(self.rng.choices(pairs, weights)[0])
        prices = {(p.category.slug, p.item.name): p for p in
                  ServicePrice.objects.select_related("category", "item")}
        return [(prices[k], self.rng.randint(1, 3) if k[0] in ("dry-clean", "shoe-cleaning", "home-textiles")
                 else self.rng.randint(2, 6)) for k in picks]

    def _book(self, customer, pickup_date):
        slots = list(TimeSlot.objects.filter(is_active=True))
        self.rng.shuffle(slots)
        basket = self._basket()
        coupon = self.rng.choice(["", "", "", "", "WELCOME50", "FRESH20"])
        is_express = self.rng.random() < 0.2
        booked_at = timezone.make_aware(datetime.datetime.combine(pickup_date - datetime.timedelta(days=1),
                                                                  datetime.time(19, 30)))
        for slot in slots:
            for code in (coupon, ""):  # if the coupon can't be used, book without it
                try:
                    return create_order(customer=customer, address=customer.addresses.first(), pickup_date=pickup_date,
                                        time_slot=slot, selected_items=basket, is_express=is_express,
                                        coupon_code=code, note=self.rng.choice(["", "", "Call before coming",
                                                                                "Security will collect"]),
                                        now=booked_at)
                except BookingError:
                    continue
        raise RuntimeError("No free slot for demo order")

    def _tag_all(self, order, staff):
        """Tag every booked piece as a garment, some with a stain or damage note."""
        pieces = []
        for line in order.items.select_related("category", "item"):
            sp = ServicePrice.objects.get(category=line.category, item=line.item)
            pieces += [sp] * line.quantity
        for sp in pieces:
            issue = self.rng.random()
            add_garment(order, sp, staff,
                        description=self.rng.choice(["", "White", "Blue", "Black", "Maroon", "Grey, Raymond",
                                                     "Printed cotton"]),
                        has_stain=issue < 0.12, has_damage=0.12 <= issue < 0.16,
                        condition_note=self.rng.choice(STAINS) if issue < 0.12 else
                        (self.rng.choice(DAMAGE) if issue < 0.16 else ""))

    def build_order(self, customer, target, days_ago, mismatch=None):
        """mismatch: None, 'store' (agent counted one more than tagged) or 'delivery'."""
        store = customer.addresses.first().area.store
        staff, agent = self.staff[store.pk], self.rng.choice(self.agents[store.pk])
        order = self._book(customer, self.today - datetime.timedelta(days=days_ago))

        if target == S.CANCELLED:
            if self.rng.random() < 0.4:
                order = assign_pickup_agent(order, agent, staff)
            return cancel_order(order, by=customer, reason=self.rng.choice(
                ["Not at home that day", "Booked by mistake", "Will send next week"]))
        rank = FLOW_RANK[target]
        if rank >= FLOW_RANK[S.PICKUP_ASSIGNED]:
            order = assign_pickup_agent(order, agent, staff)
        if rank >= FLOW_RANK[S.PICKED_UP]:
            booked_pieces = sum(i.quantity for i in order.items.all())
            order = confirm_pickup(order, agent, booked_pieces + (1 if mismatch == "store" else 0))
        if rank >= FLOW_RANK[S.AT_STORE]:
            order = change_status(order, S.AT_STORE, staff, note="Received at store")
        if rank >= FLOW_RANK[S.TAGGED]:
            self._tag_all(order, staff)
            order = finish_tagging(order, staff, confirm_mismatch=True)
        if rank >= FLOW_RANK[S.IN_CLEANING]:
            order = change_status(order, S.IN_CLEANING, staff, note="Start cleaning")
        if rank >= FLOW_RANK[S.READY]:
            order = change_status(order, S.READY, staff, note="Mark ready for delivery")
            if target != S.READY or self.rng.random() < 0.7:  # leave some Ready orders to assign
                order = assign_delivery_agent(order, agent, self.today, staff)
        if rank >= FLOW_RANK[S.OUT_FOR_DELIVERY]:
            order = start_delivery(order, agent)
        if rank >= FLOW_RANK[S.DELIVERED]:
            tagged = order.garments.count()
            count = tagged - 1 if mismatch == "delivery" else tagged
            order = confirm_delivery(order, agent, count, confirm_mismatch=True,
                                     payment_method="upi" if self.rng.random() < 0.3 else "cash",
                                     reference=f"UPI{self.rng.randint(10**9, 10**10 - 1)}")
        return order

    def make_orders(self):
        plan = [(status, days) for status, days, n in PLAN for _ in range(n)]
        # Plan positions 0-29 are Delivered, 49-50 Tagged, 54-56 Ready (see PLAN).
        mismatches = {3: "store", 17: "delivery", 49: "store", 55: "store"}  # a few, to demo the alerts
        made = []
        for i, (status, days) in enumerate(plan):
            customer = self.customers[i % len(self.customers)]
            order = self.build_order(customer, status, days, mismatches.get(i))
            self.backdate(order)
            made.append(order)
        # Delivered orders' alerts were looked into by admin; recent ones stay open for the demo.
        for alert in MismatchAlert.objects.filter(order__status=S.DELIVERED, status=MismatchAlert.Status.OPEN):
            resolve_alert(alert, self.admin, "Checked with agent and customer: counting error, all garments returned")
        return made

    # -------------------------------------------------------------- timeline ----
    def backdate(self, order):
        """Move the order's timestamps to when these steps would really have happened."""
        order = Order.objects.select_related("pickup_slot__time_slot").get(pk=order.pk)
        slot_start = timezone.make_aware(datetime.datetime.combine(order.pickup_slot.date,
                                                                   order.pickup_slot.time_slot.start_time))
        booked_at = slot_start - datetime.timedelta(hours=self.rng.randint(14, 30))
        history = list(order.history.order_by("id"))
        times = {}
        for k, h in enumerate(history):
            if h.to_status == S.BOOKED:
                t = booked_at
            elif h.to_status == S.PICKUP_ASSIGNED:
                t = booked_at + datetime.timedelta(hours=2)
            elif h.to_status == S.CANCELLED:
                t = booked_at + datetime.timedelta(hours=3)
            else:
                hours = STEP_HOURS[h.to_status][1 if order.is_express else 0]
                t = slot_start + datetime.timedelta(hours=hours, minutes=self.rng.randint(0, 40))
            # Never in the future: squeeze recent steps just before "now", still in order.
            t = min(t, self.now - datetime.timedelta(minutes=5 * (len(history) - k)))
            times[h.to_status] = t
            OrderStatusHistory.objects.filter(pk=h.pk).update(changed_at=t)

        last = max(times.values())
        Order.objects.filter(pk=order.pk).update(created_at=times[S.BOOKED], updated_at=last)
        if S.DELIVERED in times:
            Order.objects.filter(pk=order.pk).update(delivery_date=timezone.localdate(times[S.DELIVERED]))
            Payment.objects.filter(order=order).update(collected_at=times[S.DELIVERED])
        for cp, st in (("pickup", S.PICKED_UP), ("store", S.TAGGED), ("delivery", S.DELIVERED)):
            if st in times:
                CountCheck.objects.filter(order=order, checkpoint=cp).update(recorded_at=times[st])
        if S.TAGGED in times:
            Garment.objects.filter(order=order).update(tagged_at=times[S.TAGGED] - datetime.timedelta(minutes=20))
        for alert in MismatchAlert.objects.filter(order=order):
            when = times.get(S.DELIVERED if alert.checkpoint == "delivery" else S.TAGGED, last)
            MismatchAlert.objects.filter(pk=alert.pk).update(created_at=when)

    # ----------------------------------------------------------------- report ----
    def report(self, made):
        by_status = {}
        for o in made:
            by_status[o.get_status_display()] = by_status.get(o.get_status_display(), 0) + 1
        revenue = sum((p.amount for p in Payment.objects.filter(order__in=made)), Decimal("0"))
        self.stdout.write(self.style.SUCCESS(
            f"Demo data loaded: 20 customers, {len(made)} orders, {Garment.objects.filter(order__in=made).count()} "
            f"tagged garments, Rs. {revenue} collected."))
        self.stdout.write("Orders by status: " + ", ".join(f"{k} {v}" for k, v in by_status.items()))
        self.stdout.write(f"All demo logins use the password: {DEMO_PASSWORD}")
        self.stdout.write(f"  Admin     {ADMIN_PHONE}")
        for store in self.stores:
            self.stdout.write(f"  {store.name:<18} staff {self.staff[store.pk].phone}  agents "
                              + ", ".join(a.phone for a in self.agents[store.pk]))
        self.stdout.write(f"  Customers {CUSTOMER_PHONE.format(1)} ... {CUSTOMER_PHONE.format(len(self.customers))}")
