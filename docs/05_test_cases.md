# Test Cases

**Automated tests:** `venv\Scripts\python manage.py test` runs **138 tests** on a temporary PostgreSQL
database. Last run: **02 Oct 2026, result `OK` (all 138 passed)**. The cases below come from those
tests; the last column names the test method, so the examiner can see it in the code.

**Manual tests (MT-…)** are UI checks in the browser. Fill in *Actual* and *Status* after doing them,
and take the matching screenshot (see `06_screenshots.md`).

## A. Accounts & roles

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-01 | Phone number is normalised | "+91 98765-43210" | Saved as 9876543210 | As expected | Pass | `accounts.UserModelTests.test_phone_is_normalised` |
| TC-02 | DB rejects an invalid phone | phone "1234567890" inserted directly | IntegrityError (CHECK constraint) | As expected | Pass | `test_db_rejects_invalid_phone` |
| TC-03 | Email optional but unique | two blank emails; then "a@b.com" and "A@b.com" | Blanks allowed; second address rejected | As expected | Pass | `test_email_optional_but_unique` |
| TC-04 | Registration creates a Customer | valid name, phone with space, strong password | User created, in Customer group, logged in | As expected | Pass | `test_register_creates_customer_and_logs_in` |
| TC-05 | Registration rejects bad / duplicate phone | "12345"; an existing number | Form error on phone, no user created | As expected | Pass | `test_register_rejects_duplicate_and_bad_phone` |
| TC-06 | Login accepts formatted number | "+91 98765 43210" + password | Logged in (302 redirect) | As expected | Pass | `test_login_with_formatted_phone` |
| TC-07 | Protected page needs login | open /account/ logged out | Redirect to login page | As expected | Pass | `test_account_page_needs_login` |
| TC-08 | Wrong role blocked | Customer opens a staff-only view | 403 Access denied | As expected | Pass | `accounts.RoleRequiredTests.test_wrong_role_gets_403` |

## B. Public pages, catalog & store locator

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-09 | Public pages load | /, /services/, /about/, /faq/, /contact/ | HTTP 200 for each | As expected | Pass | `core.PublicPagesTests.test_public_pages_load` |
| TC-10 | Contact form validation | empty name, phone "123", bad email, message "hi" | 5 field errors, nothing saved | As expected | Pass | `core.ContactFormTests.test_invalid_message_is_rejected` |
| TC-11 | Valid contact message | correct details | Saved + email to support | As expected | Pass | `test_valid_message_is_saved_and_emailed` |
| TC-12 | One price per service + item | duplicate (Dry Clean, Saree) price | IntegrityError | As expected | Pass | `catalog.CatalogDataTests.test_one_price_per_category_and_item` |
| TC-13 | Price must be positive | price 0 | IntegrityError | As expected | Pass | `test_price_must_be_positive` |
| TC-14 | Express price | Silk saree ₹299, express +50% | ₹448.50 | As expected | Pass | `catalog.ExpressPriceTests.test_express_price_adds_surcharge` |
| TC-15 | Price list search | service = dry-clean, q = "saree" | Only Dry Clean sarees listed | As expected | Pass | `test_filter_by_category_and_search` |
| TC-16 | HTMX returns fragment only | price list with HX-Request header | Table only, no `<html>` | As expected | Pass | `test_htmx_request_returns_fragment_only` |
| TC-17 | Indian money format | 1499; 123456.5 | ₹1,499; ₹1,23,456.50 | As expected | Pass | `catalog.RupeesFilterTests.test_indian_number_format` |
| TC-18 | Served pincode | 411057 | "Great news", Baner store only | As expected | Pass | `stores.StoreLocatorTests.test_served_pincode` |
| TC-19 | Unserved pincode | 400001 | "Sorry, we don't serve…", no stores | As expected | Pass | `test_unserved_pincode` |
| TC-20 | Invalid pincode | "4110" | Error "exactly 6 digits" | As expected | Pass | `test_bad_pincode_rejected` |
| TC-21 | Store hours constraint | closing 08:00 before opening 21:00 | IntegrityError | As expected | Pass | `stores.StoreDataTests.test_store_must_close_after_opening` |

## C. Order total & coupons

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-22 | Simple total | 5 shirts (₹35) + 1 silk saree (₹299) | Subtotal ₹474, total ₹474 | As expected | Pass | `orders.OrderTotalTests.test_simple_total` |
| TC-23 | Express only where offered | 2 shirts + 1 pair sports shoes, express on | Express ₹35 (shirts only), total ₹504 | As expected | Pass | `test_express_charge_only_on_services_with_express` |
| TC-24 | Flat coupon | WELCOME50 on ₹400 | Discount ₹50 | As expected | Pass | `orders.CouponRuleTests.test_flat_discount` |
| TC-25 | Percent coupon with cap | FRESH20 on ₹500 and ₹2000 | ₹100 and ₹150 (cap) | As expected | Pass | `test_percent_discount_with_cap` |
| TC-26 | Minimum order value | WELCOME50 on ₹250 | Error "Add items worth ₹49.00 more" | As expected | Pass | `test_minimum_order_value` |
| TC-27 | Expired / inactive coupon | MONSOON15; deactivated coupon | "expired"; "no longer active" | As expected | Pass | `test_expired_and_inactive` |
| TC-28 | Per-user and total limits | use WELCOME50 twice; limit 0 | "already used"; "fully used" | As expected | Pass | `test_per_user_and_total_limits` |
| TC-29 | Cancelled order frees coupon | cancel order that used WELCOME50 | Coupon usable again | As expected | Pass | `test_cancelled_order_gives_coupon_back` |
| TC-30 | Discount never exceeds bill | ₹500 coupon on ₹120 | Discount ₹120 | As expected | Pass | `test_discount_never_exceeds_amount` |
| TC-31 | Total must add up (DB) | set total = 1 directly | IntegrityError (CHECK) | As expected | Pass | `orders.StatusHistoryTriggerTests.test_total_must_add_up_in_db` |

## D. Slot capacity

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-32 | Slot can't be overbooked | 6th booking in a 5-place slot | "Sorry, this slot just got full", count stays 5 | As expected | Pass | `orders.SlotCapacityTests.test_slot_cannot_be_overbooked` |
| TC-33 | Capacity is per area | full slot in Kothrud, book Baner | Baner booking succeeds | As expected | Pass | `test_capacity_is_per_area` |
| TC-34 | Cancel releases the place | capacity 1: book, book again, cancel, book | 2nd fails, 3rd succeeds | As expected | Pass | `test_cancel_releases_place` |
| TC-35 | Past / far slots rejected | 10:00 slot at 10:30; date +30 days | "already started"; "within the next 7 days" | As expected | Pass | `test_past_and_too_far_slots_rejected` |
| TC-36 | Failed booking takes no place | booking with coupon below minimum | Error, slot count unchanged (rollback) | As expected | Pass | `test_failed_booking_takes_no_place` |

## E. Status transitions & history

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-37 | Full lifecycle allowed | Booked → … → Delivered | Reaches Delivered | As expected | Pass | `orders.StatusTransitionTests.test_full_happy_path` |
| TC-38 | Skipping a step rejected | Booked → Ready | InvalidTransition | As expected | Pass | `test_skipping_a_step_is_rejected` |
| TC-39 | No change after Cancelled | Cancelled → Pickup Assigned | InvalidTransition | As expected | Pass | `test_no_change_after_delivered_or_cancelled` |
| TC-40 | No cancel after pickup | cancel a Picked Up order | "already been picked up" | As expected | Pass | `test_cannot_cancel_after_pickup` |
| TC-41 | Trigger logs changes with user | book, then assign agent with note | 2 history rows, correct users and note | As expected | Pass | `test_booking_and_changes_are_logged_with_user` |
| TC-42 | Direct SQL change still logged | UPDATE status without the app | History row with empty user | As expected | Pass | `test_direct_database_update_is_still_logged` |
| TC-43 | Agent required before trip | Booked → Pickup Assigned without agent | "Assign a pickup agent first" | As expected | Pass | `delivery.AssignmentTests.test_pickup_assigned_needs_an_agent` |

## F. Booking pages & addresses

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-44 | Booking needs an address | customer without address opens Book | Redirect to Add address | As expected | Pass | `orders.BookingPageTests.test_no_address_redirects_to_add_address` |
| TC-45 | Book end to end | 10 shirts, tomorrow 4 PM | Order WO-…, total ₹350, Kothrud store | As expected | Pass | `test_book_order_end_to_end` |
| TC-46 | Booking without items | all quantities 0 | "Please add at least one item" | As expected | Pass | `test_booking_without_items_shows_error` |
| TC-47 | Can't use another's address | address id of another customer | Form error on address | As expected | Pass | `test_cannot_use_someone_elses_address` |
| TC-48 | Only own orders visible | other customer opens order URL | 404 | As expected | Pass | `test_customer_sees_only_own_orders` |
| TC-49 | One default address (DB) | two default addresses for one user | IntegrityError (partial unique index) | As expected | Pass | `orders.AddressBookTests.test_db_rejects_two_defaults` |

## G. Garment tagging & final bill

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-50 | Sequential unique tag codes | tag 3 garments | WO-…-01, -02, -03; duplicate rejected | As expected | Pass | `tagging.GarmentTaggingTests.test_tag_codes_are_sequential_and_unique` |
| TC-51 | Tag only At Store | tag a Booked order | "only be tagged while the order is At Store" | As expected | Pass | `test_cannot_tag_before_order_reaches_store` |
| TC-52 | Stain needs a note | stain ticked, empty note | Error; DB CHECK also rejects | As expected | Pass | `test_stain_needs_a_note` |
| TC-53 | Booked price kept | price changed after booking | Garment uses booked ₹35 | As expected | Pass | `test_booked_price_is_used_for_booked_items` |
| TC-54 | Final bill from garments | booked 3 shirts; tagged 4 shirts + 1 saree | Estimate ₹105, final ₹439 | As expected | Pass | `tagging.FinalBillTests.test_final_bill_from_tagged_garments` |
| TC-55 | Express + coupon recalculated | 2 sarees express + WELCOME50, 1 arrives | ₹299 + ₹149.50 − ₹50 = ₹398.50 | As expected | Pass | `test_express_and_coupon_recalculated` |
| TC-56 | Coupon dropped below minimum | 10 shirts booked, 5 arrive | Discount ₹0, total ₹175 | As expected | Pass | `test_coupon_dropped_if_final_amount_below_minimum` |
| TC-57 | Staff see only their store | Baner staff opens Kothrud order | 404 | As expected | Pass | `tagging.StaffPanelViewTests.test_staff_sees_only_own_store` |
| TC-58 | Tag with photo via HTMX | stain + note + JPEG | Row with QR returned, photo saved | As expected | Pass | `test_staff_flow_receive_tag_with_photo_finish` |

## H. Garment count mismatch

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-59 | Matching counts | pickup 3, tagged 3 | No alert | As expected | Pass | `tagging.GarmentCountMismatchTests.test_matching_counts_raise_no_alert` |
| TC-60 | Store count lower than pickup | pickup 5, tagged 4 | Needs confirmation; alert (5→4, −1); email to admin | As expected | Pass | `test_store_count_lower_than_pickup_raises_alert_and_emails_admin` |
| TC-61 | Delivery vs store count | store 3, delivered 2 | Alert at delivery; recount 3 → no new alert | As expected | Pass | `test_delivery_count_compared_with_store_count` |
| TC-62 | Same wrong count twice | store count 3 entered twice (pickup 4) | Only one alert | As expected | Pass | `test_same_wrong_count_twice_gives_one_alert` |
| TC-63 | Alert needs different counts (DB) | alert with expected = actual | IntegrityError | As expected | Pass | `test_alert_needs_different_counts_in_db` |
| TC-64 | Admin resolves alert | note "Agent miscounted" | Status Resolved, resolved_by = admin | As expected | Pass | `test_admin_resolves_alert` |

## I. Delivery agent

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-65 | Agent must belong to store | Baner agent for a Kothrud order | "works at this order's store" | As expected | Pass | `delivery.AssignmentTests.test_agent_must_work_at_order_store` |
| TC-66 | Confirm pickup with count | count 4 | Picked Up, pickup count 4 saved | As expected | Pass | `delivery.AgentJobTests.test_confirm_pickup_records_count` |
| TC-67 | Other agent can't confirm | another agent confirms | "not assigned to you" | As expected | Pass | `test_other_agent_cannot_confirm` |
| TC-68 | Delivery mismatch | store 3, agent counts 2 | Blocked until confirmed; then alert (3→2) | As expected | Pass | `test_delivery_count_mismatch_needs_confirmation_and_alerts` |
| TC-69 | Jobs for the day | pickup tomorrow | Not today; listed tomorrow; still listed later (overdue) | As expected | Pass | `test_agent_jobs_for_the_day` |
| TC-70 | Full journey (all panels) | book → assign → pickup 3 → tag 3 → deliver 3 | Delivered; counts pickup 3, store 3, delivery 3 | As expected | Pass | `delivery.AgentPanelViewTests.test_full_journey_through_all_panels` |

## J. Payment, invoice & email

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-71 | Delivery needs payment | confirm delivery without payment | "Collect ₹369.00…", status unchanged | As expected | Pass | `payments.CashOnDeliveryTests.test_delivery_needs_payment` |
| TC-72 | Payment recorded | UPI, ref UPI123 | Payment ₹369 UPI by agent; Delivered | As expected | Pass | `test_payment_recorded_with_delivery` |
| TC-73 | No double payment | record payment twice | "already recorded" | As expected | Pass | `test_cannot_pay_twice_or_before_final_bill` |
| TC-74 | Invoice lines add up | express order | Σ lines = subtotal; subtotal + express − discount = total | As expected | Pass | `payments.InvoiceTests.test_invoice_lines_add_up_to_subtotal_for_express` |
| TC-75 | Invoice access | other customer / other-store staff / own staff | 404 / 404 / 200 | As expected | Pass | `test_invoice_access_rules` |
| TC-76 | Delivered email with invoice | confirm delivery | Email "Delivered" with INV-….pdf attached | As expected | Pass | `payments.EmailNotificationTests.test_delivered_email_has_invoice_attached` |
| TC-77 | Mail failure safe | SMTP error while booking | Order still saved | As expected | Pass | `test_mail_failure_does_not_break_the_order` |

## K. Dashboard & demo data

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-78 | Demo data complete | `seed_demo` | 20 customers, 60 orders, all 10 statuses, 2 agents per store | As expected | Pass | `dashboard.SeedDemoTests.test_counts_and_every_status_present` |
| TC-79 | Demo timeline valid | — | No future times; history in order | As expected | Pass | `test_timeline_is_in_the_past_and_in_order` |
| TC-80 | Revenue view correct | — | View total = sum of payments | As expected | Pass | `test_revenue_view_matches_payments` |
| TC-81 | Dashboard numbers | — | 30 daily + 12 monthly values; status counts = order count | As expected | Pass | `dashboard.DashboardTests.test_kpis_and_charts` |
| TC-82 | Dashboard access | admin; staff | 200; 403 | As expected | Pass | `test_only_admin_can_open` |

## L. Manual UI tests (fill in after testing in the browser)

| ID | Description | Steps | Expected | Actual | Status |
|---|---|---|---|---|---|
| MT-01 | Mobile layout | Open home page; F12 → Ctrl+Shift+M (phone view) | Menu folds into ☰; cards stack | | |
| MT-02 | Live estimate | Booking page: type 5 next to Shirt (Wash & Iron) | Estimate shows ₹175 without reload | | |
| MT-03 | Slot list reload | Change pickup date | Slot buttons reload; started slots "Not available" | | |
| MT-04 | Live status refresh | Keep order page open; advance status in admin | Page updates within 15 s | | |
| MT-05 | Instant tagging | Staff: tag a garment | Row with QR appears without reload | | |
| MT-06 | Print tags | Click Print tags | Label sheet with QR codes opens | | |
| MT-07 | QR scan | Scan a printed QR with a phone on the same network | Garment page opens (after staff login) | | |
| MT-08 | Agent phone screens | Log in as agent on a phone | Call / Directions / Confirm buttons usable | | |
| MT-09 | Invoice PDF | Open invoice after delivery | PDF shows PAID, totals add up | | |
| MT-10 | Dashboard charts | Log in as admin 9044000001 | 4 charts drawn; "Show as table" works | | |
| MT-11 | start.bat | Double-click start.bat | Browser opens WashO; window says "WashO is running" | | |
| MT-12 | Second laptop | Follow README "Run on a new computer" | Site runs with demo data | | |
