"""PDF invoice, drawn with ReportLab (pure Python, no browser or system libraries needed)."""
from io import BytesIO

from django.db.models import Count
from django.utils import timezone
from django.utils.html import escape as e  # user text must not break ReportLab's mini-HTML
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.templatetags.money import format_inr

BRAND = colors.HexColor("#0a3d91")
ACCENT = colors.HexColor("#14b8a6")


def rs(value):
    # The built-in PDF fonts have no ₹ glyph, so invoices use "Rs." (standard on Indian bills).
    return format_inr(value, symbol="Rs. ", always_paise=True)


def invoice_number(order):
    return f"INV-{order.code}"


def invoice_lines(order):
    """One line per (service, item, price): e.g. 'Wash & Iron – Shirt  × 4'.

    Built from the tagged garments, which are the final bill.
    """
    # Lines show the normal price; the express surcharge is shown once in the totals,
    # so the lines add up exactly to "Items" (the subtotal).
    rows = (order.garments.values("category__name", "item__name", "unit_price")
            .annotate(qty=Count("id")).order_by("category__name", "item__name"))
    return [{
        "name": e(f"{r['item__name']} ({r['category__name']})"),
        "qty": r["qty"],
        "rate": r["unit_price"],
        "amount": r["unit_price"] * r["qty"],
    } for r in rows]


def build_invoice_pdf(order):
    """Return the invoice as PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"WashO invoice {invoice_number(order)}", author="WashO")
    ss = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=ss["Normal"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=normal, fontSize=8, textColor=colors.grey)
    right = ParagraphStyle("r", parent=normal, alignment=TA_RIGHT)
    h_brand = ParagraphStyle("b", parent=ss["Title"], fontSize=22, leading=26, textColor=BRAND, alignment=0,
                             spaceBefore=0, spaceAfter=2)

    store = order.store
    payment = getattr(order, "payment", None)
    delivered_at = order.history.filter(to_status="delivered").values_list("changed_at", flat=True).first()
    story = []

    # --- Header: brand + invoice details --------------------------------------------
    header = Table([[
        [Paragraph("Wash<font color='#14b8a6'>O</font>", h_brand),
         Paragraph(f"{e(store.name)}<br/>{e(store.address)}, {e(store.locality)}, {e(store.city.name)} - {store.pincode}"
                   f"<br/>Phone: {e(store.phone)}", small)],
        [Paragraph("<b>INVOICE</b>", ParagraphStyle("i", parent=right, fontSize=16, textColor=BRAND, leading=20)),
         Paragraph(f"Invoice no: <b>{invoice_number(order)}</b><br/>Order no: {order.code}<br/>"
                   f"Date: {timezone.localtime(delivered_at or timezone.now()):%d %b %Y}", right)],
    ]], colWidths=[100 * mm, 74 * mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [header, Spacer(1, 8 * mm)]

    # --- Bill to ------------------------------------------------------------------------
    cust = order.customer
    story += [
        Paragraph("<b>Bill to</b>", normal),
        Paragraph(f"{e(cust.get_full_name() or 'Customer')} · {cust.phone}"
                  + (f" · {e(cust.email)}" if cust.email else ""), normal),
        Paragraph(e(order.address_snapshot), normal),
        Paragraph(f"Pickup: {order.pickup_slot.date:%d %b %Y}, {order.pickup_slot.time_slot}"
                  + (" · <b>EXPRESS</b>" if order.is_express else ""), small),
        Spacer(1, 6 * mm),
    ]

    # --- Lines --------------------------------------------------------------------------
    data = [["#", "Item (service)", "Qty", "Rate", "Amount"]]
    for i, line in enumerate(invoice_lines(order), 1):
        data.append([i, Paragraph(line["name"], normal), line["qty"], rs(line["rate"]), rs(line["amount"])])
    lines = Table(data, colWidths=[10 * mm, 92 * mm, 16 * mm, 28 * mm, 28 * mm], repeatRows=1)
    lines.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f7fd")]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story += [lines, Spacer(1, 4 * mm)]

    # --- Totals -------------------------------------------------------------------------
    garment_count = order.garments.count()
    totals = [["Items", f"{garment_count} pcs", rs(order.subtotal)]]
    if order.express_charge:
        totals.append(["Express charge (faster delivery)", "", rs(order.express_charge)])
    if order.discount:
        totals.append([f"Coupon {order.coupon.code}" if order.coupon else "Discount", "", f"- {rs(order.discount)}"])
    totals.append(["Pickup & delivery", "", "Free"])
    totals.append(["Total", "", rs(order.total)])
    t = Table(totals, colWidths=[118 * mm, 28 * mm, 28 * mm])
    t.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("LINEABOVE", (0, -1), (-1, -1), 1, BRAND),
        ("TOPPADDING", (0, -1), (-1, -1), 6),
    ]))
    story += [t, Spacer(1, 6 * mm)]

    # --- Payment status -----------------------------------------------------------------
    if payment:
        status = (f"<font color='#198754'><b>PAID</b></font> - {rs(payment.amount)} by "
                  f"{payment.get_method_display().lower()} on {timezone.localtime(payment.collected_at):%d %b %Y}")
        if payment.reference:
            status += f" (ref. {e(payment.reference)})"
    elif order.total <= 0:
        status = "<font color='#198754'><b>PAID</b></font> - fully covered by coupon"
    else:
        status = f"<font color='#b02a37'><b>PAYMENT DUE</b></font> - {rs(order.total)}, cash or UPI on delivery"
    story += [Paragraph(status, ParagraphStyle("p", parent=normal, fontSize=10.5)), Spacer(1, 10 * mm)]

    story.append(Paragraph(
        f"Every garment in this order was tagged and counted at pickup, at the store and at delivery. "
        f"Questions? Call {e(store.phone)} quoting order {order.code}. "
        "This is a computer-generated invoice and needs no signature.", small))

    doc.build(story)
    return buf.getvalue()
