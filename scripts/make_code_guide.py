"""Build docs/WashO_Code_Guide.pdf: which files to open in the viva, explained simply, with examples.

Run:  venv\\Scripts\\python scripts\\make_code_guide.py
Line numbers and code pieces are read from the real files every time, so the guide never goes stale.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "WashO_Code_Guide.pdf"
BLUE = colors.HexColor("#0a3d91")
LIGHT = colors.HexColor("#f3f7fd")

# Each entry: what to open, where, why the teacher might ask, a kid-simple explanation, and an example.
ITEMS = [
    dict(
        title="Settings: how WashO connects to the database",
        file="washo/settings.py", find="DATABASES = {", lines=10,
        ask="\"Where is the database connection?\" / \"Where are passwords kept?\"",
        kid="Settings is like the instruction sheet stuck on the fridge. It tells WashO: \"Our database is "
            "PostgreSQL, its name is washo, and the password is in the secret .env file.\" The real password is "
            "never written in the code. The code only says \"go and read it from .env\", the same way you'd keep "
            "your locker key in your pocket and not write the code on the locker.",
        example="The line NAME: config(\"DB_NAME\") means: open .env, find DB_NAME=washo, and use \"washo\". On "
                "the second laptop the same code works with a different password, because only .env changes.",
    ),
    dict(
        title="URL map: which address opens which page",
        file="washo/urls.py", find="urlpatterns = [", lines=17,
        ask="\"How does Django know which page to show?\"",
        kid="This is like the list of rooms in a school. If you go to /orders/ you reach the Orders room; "
            "/staff/ is the Staff room; /admin/ is the Principal's office. Django reads the address you typed, "
            "looks it up in this list and sends you to the right room (the right view).",
        example="Typing 127.0.0.1:8000/prices/ matches path(\"prices/\", ...) and opens the price list page.",
    ),
    dict(
        title="Custom user: login with a mobile number",
        file="accounts/models.py", find="class User(AbstractUser):", lines=30,
        ask="\"Why a custom user model?\" / \"How is login done?\"",
        kid="Normally a website asks for a username. In India people remember their phone number, so we made "
            "the phone number the login name. We also told the database two rules: a phone number must be 10 "
            "digits starting with 6, 7, 8 or 9, and two people can't share the same email. Even if someone tries "
            "to cheat and skip our form, the database itself says \"No!\".",
        example="Typing +91 98765 43210 is cleaned to 9876543210 and you can log in. Trying to save phone "
                "1234567890 fails, because it starts with 1 and the CHECK rule blocks it.",
    ),
    dict(
        title="Role check: who is allowed into which page",
        file="accounts/permissions.py", find="def role_required", lines=16,
        ask="\"How do you stop a customer opening the staff panel?\"",
        kid="Think of a security guard at a door with a list. Before letting you in, the guard asks two "
            "things: \"Are you logged in?\" (if not, go to the login page) and \"Is your name on this door's "
            "list?\" (if not, \"Access denied\", which is error 403). We put this guard on every page.",
        example="@role_required(Role.STAFF) on the staff panel: Store Staff get in, but a customer gets the "
                "403 \"Access denied\" page.",
    ),
    dict(
        title="Price of an item (and express price)",
        file="catalog/models.py", find="def unit_price(self, express=False):", lines=7,
        ask="\"How is the express price calculated?\"",
        kid="Each item has a price for each service, like a menu card: Shirt with Wash & Iron is Rs. 35. If you "
            "want it fast (Express), we add an extra percentage, like paying extra for a fast courier. The "
            "money is rounded to paise the normal way.",
        example="Silk saree Dry Clean = Rs. 299. Express is +50%, so 299 x 1.5 = Rs. 448.50.",
    ),
    dict(
        title="Coupon rules",
        file="orders/models.py", find="def check_usable(self, user, order_amount, today):", lines=30,
        ask="\"How do coupons work?\" / \"How do you stop coupon misuse?\"",
        kid="A coupon is like a discount ticket at a fair. Before accepting it, we check: Is it switched on? "
            "Is today between its start and end date? Has it been used too many times overall? Did YOU already "
            "use it? Is your bill big enough? If all answers are OK, we give the discount, but never more "
            "than your bill.",
        example="WELCOME50 = Rs. 50 off if the bill is at least Rs. 299. A Rs. 250 bill shows \"Add items worth "
                "Rs. 49.00 more\". FRESH20 = 20% off, max Rs. 150: a Rs. 2,000 bill gets Rs. 150 off, not Rs. 400.",
    ),
    dict(
        title="Order table and its safety rules",
        file="orders/models.py", find="class Order(models.Model):", lines=12,
        extra=("orders/models.py", "condition=Q(total=F(\"subtotal\")", 3),
        ask="\"Show me your main table\" / \"What constraints did you use?\"",
        kid="The Order table is the main notebook page for each order: who booked it, from where, which "
            "slot, which status, and the money. At the bottom we wrote a maths rule inside the database: total "
            "must equal subtotal + express charge - discount. If any program ever saves wrong maths, the "
            "database refuses, like a teacher who won't accept a wrong answer.",
        example="Subtotal 439 + express 219.50 - discount 131.70 = total 526.80, so it is accepted. Trying to "
                "save total = 1 is refused with an IntegrityError.",
    ),
    dict(
        title="Bill calculator (estimate)",
        file="orders/pricing.py", find="def build_quote(", lines=32,
        ask="\"How is the total calculated?\"",
        kid="This is like a shopkeeper's calculator. For each item it does quantity x price. Then it adds the "
            "express extra (only for services that offer express), then takes away the coupon discount. It "
            "doesn't save anything; it only calculates, which is why it's easy to test.",
        example="5 shirts x Rs. 35 = 175, plus 1 silk saree Rs. 299 = Rs. 474. With express: +Rs. 237. With "
                "FRESH20: -20% (max Rs. 150).",
    ),
    dict(
        title="Allowed status steps",
        file="orders/services.py", find="ALLOWED_TRANSITIONS = {", lines=14,
        ask="\"How do you control the order flow?\"",
        kid="An order moves like a board game piece: Booked -> Pickup Assigned -> Picked Up -> At Store -> "
            "Tagged -> In Cleaning -> Ready -> Out for Delivery -> Delivered. This list says which square you may "
            "move to next. You can't jump from Booked straight to Ready, and once Delivered the game is over. "
            "Cancel is only allowed before the clothes leave your home.",
        example="Booked -> Ready is rejected with \"Can't change status from Booked to Ready\".",
    ),
    dict(
        title="Slot booking without overbooking (row lock)",
        file="orders/services.py", find="def reserve_slot(date, time_slot, area):", lines=15,
        ask="\"What if two people book the last slot at the same time?\"",
        kid="Imagine a slide with only 5 turns left and two kids running for the last turn. The database "
            "puts a \"hold\" (a lock) on the counter. The first kid takes the turn, then the second kid "
            "is let in, sees \"0 left\" and is told \"Sorry, full\". That's SELECT ... FOR UPDATE: only one person "
            "can change the counter at a time.",
        example="The 10-12 slot in Kothrud has capacity 5. Bookings 1-5 succeed. Booking 6 gets \"Sorry, this "
                "slot just got full\". Cancelling one booking gives the place back.",
    ),
    dict(
        title="Change status (the ONLY door for status changes)",
        file="orders/services.py", find="def change_status(order, new_status, by, note=\"\"):", lines=24,
        ask="\"Where do you change an order's status?\"",
        kid="There is only ONE door to change an order's status, and this is it. At the door it checks: is "
            "this step allowed? Is an agent assigned before a trip? Then it whispers to the database \"Ravi "
            "is doing this\" (set_config), changes the status, and after saving, sends the customer an email.",
        example="Staff clicks \"Start cleaning\": Tagged -> In Cleaning is allowed, so it's saved, the history "
                "row is written and an email is sent.",
    ),
    dict(
        title="Create an order (one transaction)",
        file="orders/services.py", find="def create_order(", lines=40,
        ask="\"What happens when the customer clicks Confirm pickup?\"",
        kid="Booking is done as ONE package, like a sealed envelope. Inside: take a slot place, check the "
            "coupon, copy today's prices, save the order and its items. If anything fails (for example the "
            "coupon is not valid), the whole envelope is torn up and nothing is saved, not even the slot place.",
        example="A Rs. 35 order with WELCOME50 (needs Rs. 299) fails, and the slot counter stays exactly the same. "
                "That's a \"transaction rollback\".",
    ),
    dict(
        title="PostgreSQL TRIGGER: the automatic diary",
        file="orders/migrations/0002_status_history_trigger.py", find="CREATE OR REPLACE FUNCTION", lines=32,
        ask="\"Show me a database feature you used\" / \"What is a trigger?\"",
        kid="A trigger is a little robot that lives INSIDE the database. Whenever an order is created or its "
            "status changes, the robot wakes up by itself and writes a line in the history diary: old status, "
            "new status, who and when. Nobody can forget to write the diary, not even someone typing SQL "
            "directly, because the robot is always watching.",
        example="Agent confirms pickup: the diary gets \"pickup_assigned -> picked_up, by Ravi, 10:32 AM\". In "
                "the tests we changed the status with plain SQL and the robot still wrote it.",
    ),
    dict(
        title="Garment table: one row for every piece of clothing",
        file="tagging/models.py", find="class Garment(models.Model):", lines=24,
        ask="\"What is special about your project?\"",
        kid="Most laundries count a bag. We give every shirt its own name tag, like each student having a roll "
            "number. The row remembers which order it belongs to, what it is, its colour, and any stain or "
            "damage, with an optional photo. A rule says: if you tick \"stain\", you MUST write what the stain is.",
        example="Tag WO-000012-03 = Silk saree, Dry Clean, \"Turmeric stain near hem\", with a photo.",
    ),
    dict(
        title="Tag a garment (gives the next tag number)",
        file="tagging/services.py", find="def add_garment(", lines=19,
        ask="\"How is the tag code made?\"",
        kid="When staff tag a piece, the code locks the order (so two staff don't get the same number), finds "
            "the next number (01, 02, 03 ...), picks the price the customer was promised, and saves the "
            "garment as <order code>-<number>.",
        example="Order WO-000012 already has 2 garments, so the next one becomes WO-000012-03.",
    ),
    dict(
        title="Count check and mismatch alert",
        file="tagging/services.py", find="def record_count(order, checkpoint, count, by, note=\"\"):", lines=26,
        ask="\"How does the missing-clothes alert work?\"",
        kid="We count the clothes three times, like counting students when the bus leaves the school, when "
            "it reaches the zoo and when it comes back. Each count is compared with the one before it. If the "
            "numbers are different, an alarm (MismatchAlert) is created and the admin gets an email.",
        example="The agent counted 5 at pickup. The store tags only 4. An alert is made: \"expected 5, counted "
                "4, -1\", and the admin is emailed.",
    ),
    dict(
        title="Final bill from the tagged garments",
        file="tagging/services.py", find="def finalise_bill(order):", lines=15,
        ask="\"Is the customer charged on the estimate?\"",
        kid="At booking the customer only guesses (\"about 10 shirts\"). At the store we know the truth. So the "
            "final bill adds up the real garments. The coupon is checked again: if the bill became too "
            "small for the coupon, the discount goes away.",
        example="Booked 3 shirts (estimate Rs. 105); the store found 4 shirts + 1 saree, so the final bill is "
                "4 x 35 + 299 = Rs. 439.",
    ),
    dict(
        title="QR code for each tag",
        file="tagging/templatetags/qr.py", find="def qr_svg(data):", lines=10,
        ask="\"How are QR codes generated?\"",
        kid="The qrcode library turns text into a square barcode picture (drawn as SVG, which stays sharp "
            "when printed). Our QR contains the web address of that garment's page, so scanning it with "
            "a phone opens the garment's details.",
        example="The tag WO-000012-03 holds the address .../staff/tag/WO-000012-03/ inside its QR.",
    ),
    dict(
        title="Delivery + Cash on Delivery (all in one go)",
        file="delivery/services.py", find="def confirm_delivery(", lines=28,
        ask="\"How is payment recorded?\"",
        kid="At the customer's door the agent counts the clothes and collects the money. The code saves three "
            "things together: the delivery count, the payment (cash or UPI) and the status \"Delivered\". If "
            "the money isn't collected, the order can't become Delivered. Either everything is saved or nothing.",
        example="Bill Rs. 369. Without ticking \"Payment collected\" you see \"Collect Rs. 369.00 ...\". With "
                "the tick: a payment of Rs. 369 cash is saved and the order is Delivered.",
    ),
    dict(
        title="PDF invoice",
        file="payments/invoice.py", find="def build_invoice_pdf(order):", lines=14,
        ask="\"How is the invoice made?\"",
        kid="ReportLab is like a robot printer that draws a page using Python: the shop's name at the top, the "
            "customer, a table of items, the totals and PAID or PAYMENT DUE. Everything is drawn in memory "
            "and given to the browser as a PDF file.",
        example="INV-WO-000006: Saree Rs. 299 + 4 shirts Rs. 140 = Rs. 439; express +219.50; FRESH20 -131.70; "
                "total Rs. 526.80, PAID by cash.",
    ),
    dict(
        title="Email notifications",
        file="orders/notifications.py", find="def send_order_email(order_id, status):", lines=24,
        ask="\"How are customers informed?\"",
        kid="After every status change we send a short letter (email) to the customer: \"Your clothes are "
            "picked up\", \"Your bill is ready\" and so on. It is sent only AFTER the change is safely saved, "
            "and if the post office (mail server) is broken, the order is still fine.",
        example="Out for Delivery email: \"Ravi is on the way. Please keep Rs. 526.80 ready (cash or UPI).\"",
    ),
    dict(
        title="PostgreSQL VIEW: the revenue report",
        file="dashboard/migrations/0001_daily_revenue_view.py", find="CREATE OR REPLACE VIEW", lines=18,
        ask="\"Show me your second database feature\" / \"What is a view?\"",
        kid="A view is a saved question we keep asking the database: \"How much money did each store "
            "collect each day?\" It looks like a table, but it has no data of its own. Every time you look "
            "at it, it calculates the answer fresh, like a calculator that always shows today's total.",
        example="SELECT * FROM dashboard_daily_revenue; gives one row per store per day. A real row from your "
                "laptop: 2026-10-01 | WashO Baner | 1 order | Rs. 1,058.00 (dates move if the demo data is rebuilt).",
    ),
    dict(
        title="HTMX: page parts that update by themselves",
        file="templates/orders/book.html", find="hx-post=", lines=3,
        extra=("templates/orders/_order_status.html", "hx-trigger=\"every 15s\"", 1),
        ask="\"How does the price update without reloading?\"",
        kid="HTMX is like a waiter who brings only the dish you changed, not the whole meal again. When you "
            "type an item count, the browser quietly asks the server for a new estimate box and swaps just "
            "that box. The order page asks every 15 seconds \"any news?\" and updates the status by itself.",
        example="Type 5 next to Shirt and the estimate changes to Rs. 175 without the page blinking.",
    ),
    dict(
        title="Demo data command",
        file="core/management/commands/seed_demo.py", find="class Command(BaseCommand):", lines=20,
        ask="\"Where does this data come from?\"",
        kid="seed_demo is like a puppet show: it pretends to be 20 customers, staff and agents, and makes 60 "
            "orders by pressing the same buttons a real person would. So all the rules, counts and history "
            "are real. Then it moves the dates back, so the charts show six weeks of business.",
        example="venv\\Scripts\\python manage.py seed_demo --reset rebuilds all the demo data in about 20 seconds.",
    ),
    dict(
        title="Automated tests (proof that it works)",
        file="orders/tests.py", find="class SlotCapacityTests(TestCase):", lines=14,
        ask="\"How did you test it?\"",
        kid="Tests are like a robot student who answers the same exam questions every time we change "
            "something. We have 138 questions, for example \"Can a full slot take one more booking?\" "
            "The answer must be \"No\". If any answer is wrong, we know straight away.",
        example="venv\\Scripts\\python manage.py test -> \"Ran 138 tests ... OK\".",
    ),
]

QUICK = [
    ("Where is the database connection?", "washo/settings.py"),
    ("Which address opens which page?", "washo/urls.py"),
    ("Show a table / constraints", "orders/models.py (Order), accounts/models.py (User)"),
    ("How is the bill calculated?", "orders/pricing.py, tagging/services.py (finalise_bill)"),
    ("How are slots protected?", "orders/services.py (reserve_slot)"),
    ("Where is the trigger?", "orders/migrations/0002_status_history_trigger.py"),
    ("Where is the view?", "dashboard/migrations/0001_daily_revenue_view.py"),
    ("What is unique in your project?", "tagging/models.py (Garment), tagging/services.py (record_count)"),
    ("How do you check roles?", "accounts/permissions.py"),
    ("How is payment recorded?", "delivery/services.py (confirm_delivery), payments/models.py"),
    ("How is the PDF made?", "payments/invoice.py"),
    ("How did you test it?", "orders/tests.py, tagging/tests.py (run: manage.py test)"),
]


def locate(rel, needle):
    lines = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i, lines
    raise SystemExit(f"Could not find {needle!r} in {rel}")


def snippet(rel, needle, count, width=92):
    start, lines = locate(rel, needle)
    chunk = lines[start - 1:start - 1 + count]
    while chunk and not chunk[-1].strip():
        chunk.pop()
    out = []
    for n, text in enumerate(chunk, start):
        text = text.replace("\t", "    ").replace("₹", "Rs.").replace("→", "->").replace("–", "-").replace("—", "-")
        if len(text) > width:
            text = text[:width - 1] + "~"
        out.append(f"{n:>4}  {text}")
    return start, "\n".join(out)


def build():
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["Normal"], fontName="Helvetica", fontSize=10.5, leading=15)
    small = ParagraphStyle("small", parent=body, fontSize=9, leading=12, textColor=colors.HexColor("#444444"))
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName="Helvetica-Bold", fontSize=20, textColor=BLUE,
                        spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13.5, textColor=BLUE,
                        spaceBefore=10, spaceAfter=4)
    label = ParagraphStyle("label", parent=body, fontName="Helvetica-Bold", textColor=BLUE, spaceBefore=4)
    code = ParagraphStyle("code", fontName="Courier", fontSize=7.6, leading=9.6, backColor=LIGHT,
                          borderPadding=(5, 5, 5, 5), leftIndent=4, rightIndent=4, spaceBefore=4, spaceAfter=6)
    title = ParagraphStyle("title", parent=h1, fontSize=30, alignment=TA_CENTER, leading=36)
    sub = ParagraphStyle("sub", parent=body, alignment=TA_CENTER, fontSize=12, leading=18)

    def esc(t):
        return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    story = [
        Spacer(1, 50 * mm),
        Paragraph("Wash<font color='#14b8a6'>O</font>", title),
        Paragraph("Code Guide for the Viva", ParagraphStyle("t2", parent=title, fontSize=20, leading=26)),
        Spacer(1, 8 * mm),
        Paragraph("Which file to open when the teacher asks, what it does (explained so a 10-year-old "
                  "understands), and a real example for each.", sub),
        Spacer(1, 20 * mm),
        Paragraph("<b>How to open a file at a line:</b> open the WashO folder in VS Code, press "
                  "<b>Ctrl + P</b> and type the file name, then press <b>Ctrl + G</b> and type the line number.", sub),
        Spacer(1, 6 * mm),
        Paragraph("Part 1: Files to open  ·  Part 2: Simple explanations  ·  Part 3: Examples", sub),
        PageBreak(),
    ]

    # ---------------- Part 1: list of files ----------------
    story += [Paragraph("Part 1: Important files to open", h1),
              Paragraph("Keep this page open during the viva. Each row gives the file and the line to jump to.", body),
              Spacer(1, 4 * mm)]
    rows = [["#", "Open this file", "Line", "What it is"]]
    for i, it in enumerate(ITEMS, 1):
        line, _ = locate(it["file"], it["find"])
        it["line"] = line
        rows.append([str(i), Paragraph(f"<font face='Courier' size='8.5'>{esc(it['file'])}</font>", small),
                     str(line), Paragraph(esc(it["title"]), small)])
    t = Table(rows, colWidths=[9 * mm, 72 * mm, 13 * mm, 80 * mm], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [t, Spacer(1, 6 * mm), Paragraph("Quick answer: \"If the teacher asks ... open ...\"", h2)]
    q = Table([["Teacher asks", "Open"]] + [[Paragraph(esc(a), small), Paragraph(
        f"<font face='Courier' size='8'>{esc(b)}</font>", small)] for a, b in QUICK],
        colWidths=[70 * mm, 104 * mm], repeatRows=1)
    q.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [q, PageBreak()]

    # ---------------- Part 2: explanations (+ the real code) ----------------
    story += [Paragraph("Part 2: What each file does, explained simply", h1),
              Paragraph("Each block shows the real code from your project (with line numbers), then a simple "
                        "explanation.", body)]
    for i, it in enumerate(ITEMS, 1):
        _, code_txt = snippet(it["file"], it["find"], it["lines"])
        block = [Paragraph(f"{i}. {esc(it['title'])}", h2),
                 Paragraph(f"<font face='Courier' size='9'>{esc(it['file'])}</font> · line {it['line']}", small),
                 Paragraph(f"<b>Teacher may ask:</b> {esc(it['ask'])}", small),
                 Preformatted(code_txt, code)]
        if it.get("extra"):
            f2, needle2, n2 = it["extra"]
            line2, code2 = snippet(f2, needle2, n2)
            block += [Paragraph(f"also <font face='Courier' size='9'>{esc(f2)}</font> · line {line2}", small),
                      Preformatted(code2, code)]
        block += [Paragraph("In simple words", label), Paragraph(esc(it["kid"]), body)]
        story.append(KeepTogether(block))
    story.append(PageBreak())

    # ---------------- Part 3: examples ----------------
    story += [Paragraph("Part 3: Examples", h1),
              Paragraph("Real numbers from WashO. Say these out loud in the viva: examples make answers easy to "
                        "believe.", body), Spacer(1, 3 * mm)]
    for i, it in enumerate(ITEMS, 1):
        story.append(KeepTogether([Paragraph(f"{i}. {esc(it['title'])}", label),
                                   Paragraph(esc(it["example"]), body), Spacer(1, 2 * mm)]))

    story += [Spacer(1, 4 * mm), Paragraph("One full story: an order from start to end", h2)]
    journey = [
        "1. <b>Asha books</b> 4 shirts (Wash &amp; Iron) and 1 silk saree (Dry Clean), Express, coupon FRESH20. "
        "Estimate: 140 + 299 = 439; express +219.50; coupon -131.70 = <b>Rs. 526.80</b>. (orders/pricing.py)",
        "2. The 8-10 AM Kothrud slot had 5 places; now 4 are left. (orders/services.py reserve_slot)",
        "3. Staff assign agent <b>Ravi</b>: status Pickup Assigned. The trigger writes it in the diary.",
        "4. Ravi counts <b>5 garments</b> with Asha: status Picked Up. (delivery/services.py confirm_pickup)",
        "5. The store tags 5 pieces, WO-000006-01 ... -05; one saree has a stain note + photo. (tagging/services.py)",
        "6. Store count 5 = pickup count 5, so <b>no alert</b>. Final bill Rs. 526.80. Status Tagged.",
        "7. Cleaning, then Ready. Ravi is assigned for delivery and starts: Out for Delivery. Asha gets an email "
        "\"keep Rs. 526.80 ready\".",
        "8. At the door Ravi counts 5, collects <b>Rs. 526.80 cash</b> and ticks Paid: status Delivered, "
        "payment saved, and the invoice PDF is emailed. (delivery/services.py confirm_delivery)",
        "9. The admin's dashboard shows the Rs. 526.80 in today's revenue through the PostgreSQL view.",
        "<i>If the store had found only 4 pieces:</i> an alert \"expected 5, counted 4\" goes to the admin, "
        "who checks and writes how it was resolved.",
    ]
    story += [Paragraph(s, body) for s in journey]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 10 * mm, "WashO - Code Guide for the Viva")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title="WashO Code Guide for the Viva", author="WashO")
    doc.build(story, onFirstPage=lambda c, d: None, onLaterPages=footer)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
