# CLAUDE.md — Project Guide

> Brand name: **WashO** (original brand; working folder: `WashO`).
> Never use Tumbledry's name, logo, images or copied text anywhere in code, templates, seed data or docs.

## 1. Project summary
T.Y. B.Sc. Computer Science final-year project (SPPU, NEP 2020).
An online laundry & dry-cleaning platform: customers book a pickup, a delivery agent collects
clothes, store staff tag every garment individually (QR code), clean them, and the agent
delivers them back. Garment counts are checked at pickup, store and delivery; any mismatch
raises an admin alert (our key differentiator — solves the "missing clothes" problem).

The student does not write code. Every setup step must be explained in plain, simple words,
and code must carry short WHY-comments that help in the viva.

## 2. Tech stack (fixed — ask before changing)
| Layer | Choice |
|---|---|
| Language | Python 3.12+ (machine has 3.14 and 3.11; use 3.14 for the venv) |
| Framework | Django **5.2 LTS** (supported until April 2028) — confirmed by user |
| Database | PostgreSQL 17 via `psycopg[binary]` (psycopg 3) |
| Frontend | Django templates + Bootstrap 5 (CDN), Bootstrap Icons |
| Dynamic bits | HTMX (slot loading, status refresh); plain `fetch` only where HTMX doesn't fit |
| Charts | Chart.js (CDN) |
| Config | `.env` via `python-decouple`; `.env.example` committed, `.env` git-ignored |
| Payments | Razorpay **test mode** (`razorpay` SDK) + Cash on Delivery |
| PDF invoices | `xhtml2pdf` (pure Python, works on Windows without GTK) |
| QR codes | `qrcode` + Pillow |
| Email | console backend in development |
| Tests | Django `TestCase` (`python manage.py test`) |

## 3. Conventions
- Custom user model (`accounts.User`) from day one: `phone` required + unique, `email` optional.
  Login with phone number.
- Roles = Django **Groups**: `Customer`, `Store Staff`, `Delivery Agent`, `Admin`.
  Every view is protected by a role check (mixin/decorator in `accounts/permissions.py`).
- Apps (planned): `core` (public pages), `accounts`, `catalog`, `stores`, `orders`
  (booking, slots, coupons, status history), `tagging`, `delivery`, `payments`, `dashboard`,
  `support` (complaints, reviews).
- Business rules live in model methods / `services.py`, not in views — so they are testable.
- Money: `DecimalField(max_digits=10, decimal_places=2)`, never float. Currency INR (₹).
- Order status changes go through ONE function (`orders.services.change_status`) that validates
  the allowed transition, writes `OrderStatusHistory` (who + when) and sends the email.
- Server-side validation on every form (Django forms/ModelForms). CSRF always on.
- DB: 3NF, FKs with explicit `on_delete`, `CheckConstraint`/`UniqueConstraint`, indexes on
  frequently searched fields (phone, pincode, order code, status, dates, tag code).
- PostgreSQL-specific feature for viva: a SQL **VIEW** for revenue reporting and a **PL/pgSQL
  trigger** (created via `RunSQL` migrations) — both explained in simple words in comments + docs.
- Templates: `templates/base.html` + per-app folders; mobile-first, responsive Bootstrap grid.
- Comments: short, explain WHY (not what).
- Secrets only in `.env`. Never hardcode keys.
- Git: small meaningful commits, imperative messages (e.g. "Add store locator with pincode search").
- Timezone `Asia/Kolkata`; demo data is Pune-based.
- Master/reference data (roles, FAQs, catalog + prices, Pune stores/areas) is loaded by **data
  migrations** (`get_or_create`, never overwrites admin edits). `seed_demo` (Phase 8) adds only demo
  people/orders.
- HTMX partials: views return `app/_partial.html` when `core.htmx.is_htmx(request)`, else the full page;
  always wrap with `vary_on_htmx`. Pages must still work without JavaScript (plain GET forms).
- Money display: `{% load money %}{{ value|rupees }}` (Indian digit grouping).
- Order status: ONLY via `orders.services.change_status()` (locks row, validates `ALLOWED_TRANSITIONS`,
  calls `_set_audit_context` so the PL/pgSQL trigger `washo_log_order_status` (migration orders/0002) records
  who changed it). Python never inserts `OrderStatusHistory` rows. Admin status field is read-only; use actions.
- Slots: capacity per (date, TimeSlot, ServiceArea) via `DailySlot.booked_count`, reserved with
  `select_for_update` inside the booking transaction; cancel releases the place.
- Billing: `Order.estimated_total` frozen at booking; `subtotal/express_charge/discount/total` = current bill
  (estimate until Phase 4 tagging recomputes from garments and sets `bill_finalised`). Coupon discount is
  recalculated on the final amount (0 if it falls below `min_order_value`). DB CHECK: total = subtotal + express - discount.
- Tagging (`tagging` app, URLs under /staff/): `Garment` per piece, `tag_code` = `<order code>-NN`, QR (inline SVG)
  encodes the staff lookup URL. Staff/agents linked to a store via `User.store`; staff see only their store,
  Admin sees all. Counts via `tagging.services.record_count` (pickup → store → delivery; each compared with
  the previous; mismatch → `MismatchAlert` + email to admins on commit). `finish_tagging` records the store
  count, calls `finalise_bill` (garment prices; booked price reused for booked items) and moves to Tagged.
  Counts can also be entered in Django admin → Count checks (goes through record_count).
- Delivery (`delivery` app, agent URLs under /agent/, assignment POSTs used by the staff panel):
  `Order.pickup_agent/delivery_agent/delivery_date`. `change_status` refuses Pickup Assigned / Out for Delivery
  without the agent. `delivery.services`: `assign_pickup_agent` (Booked→Pickup Assigned; agent must be an active
  Delivery Agent of the order's store), `assign_delivery_agent` (Ready only), `confirm_pickup` (pickup count →
  Picked Up), `start_delivery` (→ Out for Delivery), `confirm_delivery` (delivery count, mismatch needs confirm →
  Delivered). `agent_jobs(agent, day)` includes overdue jobs. Tests: give orders an agent before moving them.
- Address chosen from served `ServiceArea`s; `Order.address_snapshot` keeps the address as on booking day.

## 3a. Portability rule (MANDATORY every phase)
The project must also run on a second Windows laptop. Before finishing ANY phase, update:
- `requirements.txt` — exact pinned versions (`==`) of every installed package, incl. dependencies
  (check with `venv\Scripts\python -m pip freeze`).
- `.env.example` — every setting the code reads via `config(...)`, with placeholders, no real secrets.
- `setup.bat` — checks Python 3.12–3.14, creates venv, installs requirements, creates `.env`,
  checks DB, migrates. Add new one-time steps here (Phase 8: `seed_demo`). Keep CRLF line endings.
- `start.bat` — daily launcher: checks venv/.env, port 8000 free, DB reachable, `migrate --noinput`,
  `pip install -r requirements.txt` (quiet; offline-safe when nothing new), opens browser via
  `scripts/open_browser.py`, runs server; pauses on any error. Add new start-time
  steps here. `create_shortcut.bat` makes the Desktop shortcut. Test with `WASHO_NO_BROWSER=1`.
- `README.md` — "Run on a new computer" section in simple steps (incl. creating the DB + user).
Verify `setup.bat` still works on a fresh copy (no `venv`, no `.env`) when it changes.

## 4. Key design decisions (agreed assumptions)
- At booking the customer gives *approximate* item counts → system shows an **estimated** total.
  The **final bill** is computed from the actual tagged garments at the store.
- Express service = surcharge (percentage) on the order.
- Pickup slots: capacity per (slot, area/store, date); booking is blocked when full
  (checked inside a DB transaction with row locking so two users can't grab the last place).
- Garment counts recorded at 3 checkpoints: pickup (agent), store (staff, from tagged items),
  delivery (agent). Any difference → `MismatchAlert` for admin.
- Order statuses: Booked → Pickup Assigned → Picked Up → At Store → Tagged → In Cleaning →
  Ready → Out for Delivery → Delivered; Cancelled allowed only before Picked Up.

## 5. Phase plan (stop after each phase, explain what was built / how to run / what to test)
- **Phase 0** – Environment setup: PostgreSQL install, DB + user, venv, Git. Step-by-step, simple words.
- **Phase 1** – Project skeleton, `.env`, custom user, groups/roles, base templates, public pages
  (home, services, about, contact, FAQ).
- **Phase 2** – Service catalog (categories, items, per-item prices, express), price list page,
  store locator with city/area/pincode search.
- **Phase 3** – Address book, booking flow, pickup slots + capacity, coupons, Order +
  OrderItem + OrderStatusHistory, customer order history & live status.
- **Phase 4** – Staff panel: incoming orders, garment tagging screen, QR codes, damage/stain
  notes with photo, count checks, mismatch alerts.
- **Phase 5** – Delivery agent panel: today's pickups/deliveries, count at pickup/delivery.
- **Phase 6** – Payments (Razorpay test + COD), PDF invoice, email notifications.
- **Phase 7** – Admin dashboard (Chart.js), revenue view (PostgreSQL VIEW), reports,
  complaints, ratings & reviews.
- **Phase 8** – Tests (totals, coupons, slot capacity, transitions, mismatch), `seed_demo`
  command (3 Pune stores, 20 customers, 60 orders, full price list), README.
- **Phase 9** – Academic docs in `/docs` (Markdown + Mermaid): synopsis, full report chapters,
  all diagrams, data dictionary, test case table, screenshot list, viva prep (40 Q&A).

## 6. Status
- [x] Phase 0  - [x] Phase 1  - [x] Phase 2  - [x] Phase 3  - [x] Phase 4
- [x] Phase 5  - [ ] Phase 6  - [ ] Phase 7  - [ ] Phase 8  - [ ] Phase 9

## 7. Common commands (filled in as we go)
```
venv\Scripts\activate          # venv uses Python 3.14
python scripts\check_db.py       # verify DB connection + permissions
python manage.py migrate
python manage.py createsuperuser    # asks for mobile number + password
python manage.py runserver
python manage.py test
python manage.py seed_demo
```
