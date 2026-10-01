from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django import template

register = template.Library()


def _indian_grouping(whole: str) -> str:
    """'1234567' -> '12,34,567' (Indian style: last 3 digits, then groups of 2)."""
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups) + "," + tail


def format_inr(value, symbol="₹", always_paise=False):
    """1499 -> '₹1,499'; 123456.5 -> '₹1,23,456.50'. Used by templates and the PDF invoice."""
    if value in (None, ""):
        return ""
    try:
        amount = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        return str(value)
    sign = "-" if amount < 0 else ""
    whole, paise = f"{abs(amount):.2f}".split(".")
    text = _indian_grouping(whole)
    if paise != "00" or always_paise:
        text += "." + paise
    return f"{sign}{symbol}{text}"


@register.filter
def rupees(value):
    """{{ price|rupees }} -> '₹1,499' or '₹1,23,456.50'. Blank for None."""
    return format_inr(value)
