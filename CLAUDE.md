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
- [x] Phase 0  - [x] Phase 1  - [ ] Phase 2  - [ ] Phase 3  - [ ] Phase 4
- [ ] Phase 5  - [ ] Phase 6  - [ ] Phase 7  - [ ] Phase 8  - [ ] Phase 9

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
