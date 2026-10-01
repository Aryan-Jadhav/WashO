"""Numbers for the admin dashboard. Revenue comes from the PostgreSQL view (DailyRevenue)."""
import datetime
from decimal import Decimal

from django.db.models import Avg, Count, F, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from orders.models import Order
from orders.services import STATUS_FLOW
from payments.models import Payment
from tagging.models import Garment, MismatchAlert

from .models import DailyRevenue

S = Order.Status
CLOSED = [S.DELIVERED, S.CANCELLED]


def _month_start(d):
    return d.replace(day=1)


def _add_months(d, n):
    m = d.month - 1 + n
    return d.replace(year=d.year + m // 12, month=m % 12 + 1, day=1)


def dashboard_data(store=None, today=None):
    today = today or timezone.localdate()
    orders = Order.objects.all()
    revenue = DailyRevenue.objects.all()
    payments = Payment.objects.all()
    garments = Garment.objects.all()
    alerts = MismatchAlert.objects.filter(status=MismatchAlert.Status.OPEN)
    if store:
        orders = orders.filter(store=store)
        revenue = revenue.filter(store=store)
        payments = payments.filter(order__store=store)
        garments = garments.filter(order__store=store)
        alerts = alerts.filter(order__store=store)

    month_start = _month_start(today)

    def rev(qs):
        return qs.aggregate(s=Sum("revenue"))["s"] or Decimal("0")

    kpis = {
        "bookings_today": orders.filter(created_at__date=today).count(),
        "open_orders": orders.exclude(status__in=CLOSED).count(),
        "delivered_today": orders.filter(history__to_status=S.DELIVERED, history__changed_at__date=today)
        .distinct().count(),
        "revenue_today": rev(revenue.filter(day=today)),
        "revenue_month": rev(revenue.filter(day__gte=month_start, day__lte=today)),
        "avg_order_value": payments.filter(collected_at__date__gte=month_start)
        .aggregate(a=Avg("amount"))["a"] or Decimal("0"),
        "open_alerts": alerts.count(),
    }

    # Daily revenue, last 30 days (days with no sales shown as 0, so the time axis is honest).
    start = today - datetime.timedelta(days=29)
    per_day = dict(revenue.filter(day__gte=start, day__lte=today).values("day")
                   .annotate(s=Sum("revenue")).values_list("day", "s"))
    daily = [{"label": (start + datetime.timedelta(days=i)).strftime("%d %b"),
              "value": float(per_day.get(start + datetime.timedelta(days=i), 0))} for i in range(30)]

    # Monthly revenue, last 12 months.
    first = _add_months(month_start, -11)
    per_month = {row["m"]: row["s"] for row in revenue.filter(day__gte=first, day__lte=today)
                 .annotate(m=TruncMonth("day")).values("m").annotate(s=Sum("revenue"))}
    monthly = []
    for i in range(12):
        m = _add_months(first, i)
        monthly.append({"label": m.strftime("%b %Y"), "value": float(per_month.get(m, 0))})

    # Orders by status, in the order an order moves through them.
    counts = dict(orders.values_list("status").annotate(n=Count("id")).values_list("status", "n"))
    by_status = [{"label": s.label, "value": counts.get(s.value, 0)} for s in STATUS_FLOW + [S.CANCELLED]]

    # Top services by garments cleaned (with the money they brought in).
    top_services = list(
        garments.values(name=F("category__name"))
        .annotate(garments=Count("id"), amount=Sum(F("unit_price") + F("express_surcharge")))
        .order_by("-garments")[:6]
    )

    return {"kpis": kpis, "daily": daily, "monthly": monthly, "by_status": by_status,
            "top_services": top_services, "today": today}


def store_summary(today=None):
    """One row per store for the comparison table."""
    from stores.models import Store

    today = today or timezone.localdate()
    month_start = _month_start(today)
    rows = []
    for st in Store.objects.filter(is_active=True):
        rows.append({
            "store": st,
            "open_orders": Order.objects.filter(store=st).exclude(status__in=CLOSED).count(),
            "revenue_month": DailyRevenue.objects.filter(store=st, day__gte=month_start)
            .aggregate(s=Sum("revenue"))["s"] or Decimal("0"),
            "open_alerts": MismatchAlert.objects.filter(order__store=st, status=MismatchAlert.Status.OPEN).count(),
        })
    return rows
