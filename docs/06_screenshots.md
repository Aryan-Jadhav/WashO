# Screenshots to capture

Start WashO with `start.bat` (demo data must be loaded). Use **Chrome or Edge**. Press **Win + Shift + S**
to take a screenshot, and save them into `docs/screenshots/` with the file names below (e.g. `S01_home.png`).
For phone-view shots, press **F12**, then **Ctrl + Shift + M**, and pick "iPhone 12 Pro" or similar.

All demo accounts use the password **Demo@1234**.

| # | File name | Login as | Page / what to show | Notes for the caption |
|---|---|---|---|---|
| S01 | home | logged out | Home page (hero, pincode check, services) | Public website |
| S02 | home_mobile | logged out | Home page in phone view | Responsive design |
| S03 | price_list | logged out | Prices → type "saree" | Live search (HTMX) |
| S04 | store_locator | logged out | Stores → search `411057` | Pincode check: served |
| S05 | store_locator_no | logged out | Stores → search `400001` | Pincode not served |
| S06 | register_errors | logged out | Sign up with phone `12345` | Server-side validation |
| S07 | login | logged out | Login page | Mobile-number login |
| S08 | customer_account | 9011000001 | My account | Customer dashboard |
| S09 | address_form | 9011000001 | Add address (locality list) | Only served areas |
| S10 | booking | 9011000001 | Book pickup with items, express on, FRESH20 | Live estimate + slots |
| S11 | booking_slots | 9011000001 | Slot buttons showing "N left" / "Full" | Slot capacity |
| S12 | my_orders | 9011000001 | My orders list | Order history |
| S13 | order_detail | a customer with a *Tagged* or later order | Order page: progress bar, history, garments, bill | Live status + transparency |
| S14 | invoice_pdf | a customer with a *Delivered* order | View invoice | PDF invoice (PAID) |
| S15 | staff_panel | 9022000002 (Kothrud staff) | Staff panel, "To tag" tab | Order queue |
| S16 | assign_agent | 9022000002 | Booked order → Agents box | Agent assignment |
| S17 | tagging | 9022000002 | Order *At Store*: tag form + garment rows with QR | Garment tagging |
| S18 | stain_photo | 9022000002 | Garment with Stain badge + photo thumbnail | Damage recorded before cleaning |
| S19 | count_warning | 9022000002 | Finish tagging with different count (warning + tick box) | Mismatch check at store |
| S20 | print_tags | 9022000002 | Print tags page | QR labels |
| S21 | garment_lookup | 9022000002 | Staff panel → type a tag code copied from S17 | QR / tag lookup |
| S22 | agent_jobs_mobile | 9033000003 (Kothrud agent) | My jobs (phone view) | Agent panel |
| S23 | agent_pickup_mobile | 9033000003 | A pickup job: count form, Call, Directions | Pickup count at door |
| S24 | agent_delivery_mobile | 9033000003 | Delivery job: "Collect ₹…", Cash/UPI, tick | Cash on Delivery |
| S25 | dashboard | 9044000001 (admin) | Dashboard: KPI tiles + charts | Admin dashboard |
| S26 | dashboard_table | 9044000001 | A chart with "Show as table" opened | Accessible data |
| S27 | alerts | 9044000001 | Mismatch alerts (open) | Automatic alerts |
| S28 | admin_site | 9044000001 | /admin/ home | Master data management |
| S29 | admin_orders | 9044000001 | Admin → Orders list with filters | Admin order list |
| S30 | admin_history | 9044000001 | Admin → Order status history | Trigger-written audit trail |
| S31 | pgadmin_trigger | — | pgAdmin: orders_order → Triggers (or `\d orders_order` in psql) | PL/pgSQL trigger exists |
| S32 | pgadmin_view | — | pgAdmin: Views → dashboard_daily_revenue → View data | PostgreSQL view |
| S33 | email_console | — | The start.bat window showing a printed status email | Email notification |
| S34 | tests_ok | — | `venv\Scripts\python manage.py test` → "Ran 138 tests … OK" | Automated testing |
| S35 | start_bat | — | The start.bat window: "WashO is running" | One-click start |

**Tip for S31–S32 (psql):** open *SQL Shell (psql)*, connect to database `washo` as `washo_user`, then run
`\d orders_order` (triggers are listed at the bottom) and `SELECT * FROM dashboard_daily_revenue LIMIT 10;`.
