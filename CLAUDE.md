# CLAUDE.md: WashO handover report

> Read this first. It is the single source of truth for any Claude session on this project.
> Brand: **WashO** (original). Never use Tumbledry's name, logo, images or copied text anywhere.

## 1. What this is
T.Y. B.Sc. Computer Science final-year project (Savitribai Phule Pune University, NEP 2020).
WashO is an online laundry & dry-cleaning platform. Customers book a doorstep pickup. A delivery
agent collects the clothes, store staff **tag every garment individually** (unique code + QR, with a
stain/damage note and photo), clean them, and the agent delivers them back and collects **Cash on
Delivery**. Garment counts are checked at **pickup → store → delivery**; any difference raises a
**mismatch alert** for admin. This is the project's key differentiator: it solves the "missing clothes" problem.

**The student does not write code.** Explain every step in plain, simple words (short sentences,
numbered steps, tell them exactly what to click or type). Code carries short WHY-comments for the viva.
Stop after each piece of work, then say what was built, how to run it and what to test in the browser.

## 2. Current status (as of 2026-10-02): ALL PHASES COMPLETE
| Phase | Status |
|---|---|
| 0 Environment | ✅ PostgreSQL 18.3, DB `washo`, user `washo_user` (owner + CREATEDB), venv on Python 3.14 |
| 1 Skeleton, custom user, roles, public pages | ✅ |
| 2 Catalog, price list, store locator | ✅ |
| 3 Addresses, booking, slots, coupons, orders, status history | ✅ |
| 4 Staff panel, garment tagging, QR, photos, counts, mismatch alerts | ✅ |
| 5 Delivery agent panel | ✅ |
| 6 Cash on Delivery, PDF invoices, email notifications | ✅ (Razorpay **dropped**: user decision) |
| 7 Admin dashboard + PostgreSQL revenue view | ✅ (complaints & reviews **dropped** → Future Enhancements; user decision) |
| 8 Tests, `seed_demo`, README | ✅ 138 tests, all passing |
| 9 Academic docs in `docs/` | ✅ synopsis, report, 13 Mermaid diagrams + PNGs, data dictionary, test cases, screenshot list, viva Q&A |

**Not yet verified by Claude (the browser extension was never connected):** live HTMX behaviour in a
real browser, the phone layout, QR scanning from a phone, and the Chart.js charts actually drawing. All
were checked server-side (HTTP responses / Django test client) only. They are listed as manual tests
MT-01…MT-12 in `docs/05_test_cases.md`, with empty Actual/Status columns for the student.

**Remaining work is the student's:** fill in name, roll no., guide and college in `docs/01_synopsis.md` and
`docs/02_project_report.md`, and adjust the Gantt dates; take the 35 screenshots (`docs/06_screenshots.md`);
do the manual tests; build the Word report from the docs plus `docs/diagrams/*.png`.

## 3. Environment facts
- Windows 11, PowerShell 5.1 (no `&&`; use `;` and `if ($?)`). Git Bash is also available.
- Project: `C:\Users\think\Desktop\WashO`. Python **3.14.3** venv in `venv\`. Always call
  `venv\Scripts\python ...` (don't rely on `activate`; PowerShell script policy may block it).
- PostgreSQL **18.3** at `C:\Program Files\PostgreSQL\18\bin` (added to the user PATH), service `postgresql-x64-18`.
- `.env` holds the real DB password and SECRET_KEY. **Never print or commit it.** `.env.example` is the template.
- GitHub: `origin` = https://github.com/Aryan-Jadhav/WashO.git, branch `main`, in sync. Push after
  committing changes (the user approved pushing to this repo).
- Git commit messages end with: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- The user's database has the demo data **plus 2 of the user's own test orders**. Don't delete their
  data. `seed_demo --reset` only touches demo phone ranges.
- The Mermaid CLI used to validate and export diagrams was installed in the session scratchpad (not in the
  project), using Edge at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe` as the browser.
  Reinstall in a temp folder with `PUPPETEER_SKIP_DOWNLOAD=true` if diagrams change.

## 4. Tech stack (fixed; ask before changing)
| Layer | Choice (exact versions in `requirements.txt`) |
|---|---|
| Language / framework | Python 3.14.3 · Django **5.2.17 LTS** |
| Database | PostgreSQL 18.3 via `psycopg[binary]` 3.3.6 |
| Frontend | Django templates + Bootstrap 5.3.8 + Bootstrap Icons 1.13.1 (CDN); Poppins font |
| Dynamic bits | HTMX 2.0.4 (CDN). Pages must still work without JavaScript |
| Charts | Chart.js 4.4.1 (CDN) on the admin dashboard |
| Config | `.env` via `python-decouple` 3.8 |
| Payments | **Cash on Delivery only** (cash or UPI to the agent) |
| PDF | `reportlab` 5.0.1 (PDFs print `Rs.`; the base fonts have no ₹ glyph) |
| QR / images | `qrcode` 8.2 (inline SVG) · `pillow` 12.3.0 (photo uploads) |
| Email | console backend in dev; SMTP settings documented in `.env.example` |
| Tests | Django `TestCase` on a real PostgreSQL test DB (`manage.py test`) |

## 5. Code map (9 apps)
| App | URL prefix | Responsibility |
|---|---|---|
| `core` | `/` | Public pages, FAQ, contact; `BootstrapFormMixin`; `money` template filter (`rupees`, `format_inr`); `htmx.py`; **`seed_demo`** command |
| `accounts` | `/account/`, `/login/` | Custom `User` (phone login, optional unique email, `store` FK for staff/agents), `Address`, `roles.py`, `permissions.py` (`role_required`, `RoleRequiredMixin`), `after_login` role routing |
| `stores` | `/stores/` | `City`, `Store`, `ServiceArea` (pincodes), store locator |
| `catalog` | `/prices/` | `ServiceCategory` (express %), `Item`, `ServicePrice`, price list |
| `orders` | `/orders/` | `TimeSlot`, `DailySlot`, `Coupon`, `Order`, `OrderItem`, `OrderStatusHistory`; `pricing.py`, **`services.py`**, `notifications.py` |
| `tagging` | `/staff/` | `Garment`, `CountCheck`, `MismatchAlert`; staff panel, QR (`templatetags/qr.py`), alerts page |
| `delivery` | `/agent/` | Agent assignment, "My jobs", pickup and delivery confirmation |
| `payments` | `/payments/` | `Payment`, `services.py`, `invoice.py` (PDF) |
| `dashboard` | `/dashboard/` | `DailyRevenue` (unmanaged model over a view), KPIs and charts |

Other: `templates/` (base, partials, one folder per app, `emails/`), `static/` (css, svg logo), `scripts/`
(`check_db.py`, `make_env.py`, `open_browser.py`, `gen_data_dictionary.py`), `docs/`,
`setup.bat` / `start.bat` / `create_shortcut.bat`.

## 6. Rules and conventions (keep following these)
- **Business rules live in `services.py`**, never in views. Views: role check → server-side form validation → service call → template.
- **Order status changes ONLY through `orders.services.change_status()`.** It locks the row, validates `ALLOWED_TRANSITIONS`,
  refuses Pickup Assigned / Out for Delivery without an agent, calls `_set_audit_context` (`set_config('washo.changed_by')`)
  and emails the customer on commit. **Python never inserts `OrderStatusHistory`**: the PL/pgSQL trigger
  `washo_log_order_status` (migration `orders/0002`) does. The admin status field is read-only; use the admin actions.
- **Slots:** capacity per (date, TimeSlot, ServiceArea) via `DailySlot.booked_count`, reserved with `select_for_update`
  inside the booking transaction; cancelling releases the place. Bookings up to 7 days ahead, at least 60 minutes before the slot starts.
- **Billing:** `estimated_total` is frozen at booking. `subtotal/express_charge/discount/total` is the current bill, which
  `tagging.services.finalise_bill` recomputes from the garments (sets `bill_finalised`; booked prices are reused for booked
  items; the coupon is re-applied and gives 0 below its minimum). DB CHECK: `total = subtotal + express_charge - discount`.
- **Counts:** `tagging.services.record_count` (pickup → store → delivery, each compared with the previous;
  mismatch → `MismatchAlert` + email to admins on commit). Staff/agents must tick a confirmation to continue with a mismatch.
- **Delivery:** `delivery.services` (`assign_pickup_agent`, `assign_delivery_agent`, `confirm_pickup`, `start_delivery`,
  `confirm_delivery`). `confirm_delivery` saves the count, the `Payment` and Delivered in ONE transaction.
- **Access:** staff and agents see only their `User.store`; Admin sees everything. Someone else's data → **404**, wrong role → **403**.
- **Emails:** `orders.notifications.send_order_email(order_id, status)` via `transaction.on_commit`; skipped if there's no
  customer email; failures are logged, never raised; the Delivered email attaches the invoice.
- **Money:** `DecimalField`, never float; show with `{% load money %}{{ v|rupees }}` (Indian grouping).
- **HTMX:** return `app/_partial.html` when `core.htmx.is_htmx(request)`, and wrap the response with `vary_on_htmx`.
- **Templates:** `{# #}` comments must be ONE line; use `{% comment %}` for longer ones (a test enforces this).
- **ReportLab:** escape all user text with `django.utils.html.escape` inside Paragraphs.
- **DB:** 3NF; explicit `on_delete`; Check/Unique constraints for the important rules; indexes on searched fields;
  soft delete (`is_active`) for addresses, stores and areas. Master data (roles, FAQs, catalog, stores, slots, coupons) comes
  from **data migrations** using `get_or_create`.
- **PostgreSQL features for the viva:** the trigger (`orders/0002`) and the VIEW `dashboard_daily_revenue` (`dashboard/0001`).
- **Tests:** add tests for every rule. Orders need an agent before they move past Booked. Use
  `captureOnCommitCallbacks(execute=True)` to test emails and alerts.
- **Charts:** single-series bars in `#0d6efd` (validated; the teal `#14b8a6` fails contrast for marks), each with a "Show as table" fallback.
- **Git:** small commits with imperative messages; then `git push`.
- **After model changes:** run `venv\Scripts\python scripts\gen_data_dictionary.py` and update the affected docs and diagrams.

## 7. Portability rule (MANDATORY after any change)
The project must also run on a second Windows laptop. Keep these up to date:
- `requirements.txt`: exact `==` pins of every package including dependencies (`pip freeze`).
- `.env.example`: every `config(...)` setting, with placeholders and no secrets.
- `setup.bat` (7 steps): Python 3.12–3.14 check → venv (rebuilt if broken) → pip install → `.env` from the template
  (then stops for the password) → DB check → migrate → `seed_demo`. CRLF line endings (`.gitattributes`).
- `start.bat`: checks venv/.env, port 8000 free, DB reachable → pip install (quiet) → `migrate --noinput` →
  opens the browser via `scripts/open_browser.py` → runserver; pauses on any error. Test with `WASHO_NO_BROWSER=1`.
- `README.md`: "Run on a new computer" in simple steps, plus demo logins and troubleshooting.

## 8. Demo data
`venv\Scripts\python manage.py seed_demo [--reset]`: 3 Pune stores (from migrations), 1 staff + 2 agents per store,
20 customers, 60 orders over 6 weeks in all 10 statuses, ~350 garments, ~₹24k collected, 2 open + 2 resolved alerts.
Orders are built through the real services, then backdated. All demo passwords: **`Demo@1234`**.

| Role | Phones |
|---|---|
| Admin | 9044000001 |
| Staff (Baner / Kothrud / Viman Nagar) | 9022000001 / 9022000002 / 9022000003 |
| Agents (Baner, Kothrud, Viman Nagar) | 9033000001-02, 9033000003-04, 9033000005-06 |
| Customers | 9011000001 … 9011000020 |

## 9. Commands
```
venv\Scripts\python manage.py test                  # 138 tests, ~2.5 minutes
venv\Scripts\python manage.py seed_demo --reset     # rebuild demo data
venv\Scripts\python scripts\check_db.py             # DB connection + permissions
venv\Scripts\python scripts\gen_data_dictionary.py  # regenerate docs/04_data_dictionary.md
venv\Scripts\python manage.py runserver             # or double-click start.bat
```

## 10. Ideas if more work is requested (each needs the user's OK)
Complaints/support tickets, ratings & reviews, online payment gateway, SMS/WhatsApp notifications, delivery time slots,
an agent mobile app with in-app QR scanning, and production deployment (Gunicorn + Nginx + HTTPS, `DEBUG=False`, backups).
