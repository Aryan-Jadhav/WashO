"""Order total calculation - pure functions, so they are easy to test.

Bill = subtotal (base prices) + express charge - coupon discount.
"""
from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from .models import Coupon, CouponError, money


@dataclass
class QuoteLine:
    service_price: object  # catalog.ServicePrice
    quantity: int
    amount: Decimal = Decimal("0.00")  # quantity x (price + express surcharge)

    @property
    def category(self):
        return self.service_price.category

    @property
    def item(self):
        return self.service_price.item

    @property
    def unit_price(self):
        return self.service_price.price

    def express_surcharge(self, is_express):
        """Extra ₹ per unit for Express (0 if the order isn't express or the service has no express)."""
        if not is_express:
            return Decimal("0.00")
        return self.service_price.unit_price(express=True) - self.service_price.unit_price()


@dataclass
class Quote:
    lines: list = field(default_factory=list)
    is_express: bool = False
    subtotal: Decimal = Decimal("0.00")
    express_charge: Decimal = Decimal("0.00")
    discount: Decimal = Decimal("0.00")
    coupon: Coupon | None = None
    coupon_error: str = ""

    @property
    def gross(self):
        return self.subtotal + self.express_charge

    @property
    def total(self):
        return self.gross - self.discount

    @property
    def piece_count(self):
        return sum(line.quantity for line in self.lines)

    @property
    def has_express_lines(self):
        return any(line.category.express_available for line in self.lines)


def build_quote(selected, is_express=False, coupon_code="", user=None, today=None):
    """Work out the bill for a list of (ServicePrice, quantity) pairs.

    The coupon is checked against the gross amount (after express, before discount).
    An invalid coupon does NOT stop the quote; the reason is put in `coupon_error`.
    """
    today = today or timezone.localdate()
    quote = Quote(is_express=is_express)
    for service_price, qty in selected:
        if qty <= 0:
            continue
        line = QuoteLine(service_price, qty)
        quote.lines.append(line)
        base = money(qty * line.unit_price)
        extra = money(qty * line.express_surcharge(is_express))
        line.amount = base + extra
        quote.subtotal += base
        quote.express_charge += extra

    coupon_code = (coupon_code or "").strip().upper()
    if coupon_code:
        coupon = Coupon.objects.filter(code=coupon_code).first()
        if coupon is None:
            quote.coupon_error = "This coupon code doesn't exist."
        else:
            try:
                coupon.check_usable(user, quote.gross, today)
                quote.coupon = coupon
                quote.discount = coupon.discount_for(quote.gross)
            except CouponError as e:
                quote.coupon_error = str(e)
    return quote
