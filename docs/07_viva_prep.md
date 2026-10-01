# Viva Preparation: 40 likely questions with short answers

Speak in your own words. Each answer is short on purpose; give the one-line answer first, then an
example from WashO if the examiner wants more.

## A. Project idea

**1. What is your project in one sentence?**
WashO is an online laundry and dry-cleaning service where customers book a doorstep pickup, every
garment is tagged with its own QR code at the store, and counts are checked at pickup, store and
delivery so no clothes go missing.

**2. What problem does it solve?**
The most common complaint about laundry services is missing clothes, because bags are counted
roughly or not at all. WashO records each garment and compares the count three times, raising an
alert automatically if anything differs.

**3. What is the unique feature compared with existing apps?**
Garment-level tagging (one record + QR per piece, with stain/damage photo before cleaning) and the
three-point count with automatic mismatch alerts. The customer can see every tagged garment.

**4. Who are the users?**
Four roles: Customer, Store Staff, Delivery Agent and Admin, plus visitors for the public pages.

**5. Why did you choose Cash on Delivery only?**
To keep the project focused and avoid handling card data. The final bill is known only after the
store tags the garments, so collecting at delivery fits the flow. The `Payment` table already
supports adding online methods later.

## B. Technology

**6. Why Django?**
It has built-in login, password hashing, admin site, ORM, form validation and CSRF protection, so I
could focus on business logic. Version 5.2 is LTS (Long Term Support), with security updates until 2028.

**7. What is MVT?**
Model–View–Template. The Model is the database table, the View is the Python function that
handles a request, and the Template is the HTML page. Django's URL dispatcher sends each request
to the right view.

**8. Why PostgreSQL and not MySQL or SQLite?**
PostgreSQL has strong support for constraints, transactions, row locking, PL/pgSQL triggers and
views, and I used all of them. SQLite isn't meant for many users at once.

**9. What is HTMX, and why not React?**
HTMX lets an HTML element fetch a small piece of HTML from the server and replace part of the page,
using attributes like `hx-get`. The live estimate, slot list, instant tagging and auto-refreshing
status work without writing a JavaScript app. It is simple to explain, and pages still work without JS.

**10. What is psycopg?**
The driver that lets Python talk to PostgreSQL. I use version 3.

**11. How are secrets kept safe?**
Passwords and the secret key are in a `.env` file read by `python-decouple`. `.env` is listed in
`.gitignore`, so it never goes into Git. `.env.example` shows the settings without real values.

## C. Database

**12. How many tables, and which are the main ones?**
21 tables plus one view (and Django's own session/permission tables). Main ones: User, Address, Store, ServiceArea, ServiceCategory, Item,
ServicePrice, TimeSlot, DailySlot, Coupon, Order, OrderItem, OrderStatusHistory, Garment,
CountCheck, MismatchAlert and Payment.

**13. Explain normalisation in your project.**
The database is in 3NF. For example, the price depends on both service and item, so it is in a separate
ServicePrice table, not in Item. A ServiceArea doesn't store its city, because the city is known
through its store; storing it twice could become inconsistent.

**14. But Order has an address copy and prices are copied. Isn't that against normalisation?**
Those are deliberate history snapshots. An invoice must show the address and prices as they were
on that day, even if the customer edits the address or the price list changes later.

**15. What is the PostgreSQL trigger in your project?**
`washo_log_order_status()` is a PL/pgSQL function that runs automatically after an order is
inserted or its status changes. It inserts a row into the status history table with the old status,
the new status, the time and the user. So the audit trail can't be skipped, even by someone
running SQL directly.

**16. How does the trigger know which user made the change?**
Before saving, Django runs `set_config('washo.changed_by', user_id, true)`. The trigger reads it with
`current_setting()`. The `true` means the value lasts only until the end of the transaction.

**17. What is the view in your project?**
`dashboard_daily_revenue` is a saved query that joins payments with orders and adds up the money
per store per day in Indian time. The dashboard reads it like a table. It stores no data, so it is
always up to date.

**18. Give examples of constraints in your database.**
- **CHECK:** `total = subtotal + express_charge − discount`; a phone must match `^[6-9]\d{9}$`; a coupon percentage ≤ 100; a stain needs a note; an alert only when the counts differ.
- **UNIQUE:** one price per service + item; one count per checkpoint.
- **Partial unique index:** one default address per user; email unique only when given.

**19. What are indexes and where did you use them?**
An index is like a book index: it makes searching fast. I used them on phone, order code, status,
pincode, tag code, (customer, date), (agent, status) and (date, area) for slots.

**20. What does on_delete PROTECT / CASCADE / SET_NULL mean?**
CASCADE deletes the children too: deleting an order deletes its items. PROTECT refuses to delete
while something refers to the row: you can't delete a store that has orders. SET_NULL keeps the row
and clears the link: if a staff user is deleted, history rows remain.

## D. Business logic

**21. How do you prevent two customers booking the last place in a slot?**
Booking runs in a transaction and locks that slot's counter row with `SELECT … FOR UPDATE`. The
second customer waits until the first finishes, then sees the slot is full. A test proves a 5-place
slot never takes a 6th booking.

**22. Why is the slot capacity per area?**
One agent covers an area in a two-hour window, so capacity is about how many homes can be visited
in that area. Each area therefore has its own count.

**23. How is the bill calculated?**
- Items = quantity × price.
- Express adds the service's surcharge (50%), but only for services that offer it.
- The coupon discount is applied on that amount, never more than the bill.
- Total = items + express − discount.

The estimate uses the customer's counts. The final bill uses the garments actually tagged.

**24. What happens if fewer garments arrive than booked?**
The final bill is made from the tagged garments, so the customer pays for what we received. The
coupon is checked again; if the amount falls below the coupon's minimum, the discount becomes 0.

**25. Explain the order status flow.**
Booked → Pickup Assigned → Picked Up → At Store → Tagged → In Cleaning → Ready → Out for Delivery →
Delivered. Cancelled is possible only before pickup. One function, `change_status`, checks the
allowed transitions; anything else is rejected.

**26. How does the mismatch alert work?**
Counts are saved at pickup (agent), at the store (number of tagged garments) and at delivery (agent).
Each is compared with the previous one. If they differ, the user must confirm they re-counted, then
a MismatchAlert is created and the admin is emailed. The admin resolves it with a written note.

**27. What is in the QR code?**
The address of that garment's page in the staff panel, `/staff/tag/<tag code>/`. Scanning it with a
phone shows the item, its condition, its order and its status. Only logged-in staff can open it.

**28. When are emails sent, and what if email fails?**
On booking and on every status change, with the invoice attached on delivery. They are sent with
`transaction.on_commit`, so only after the change is really saved. If sending fails, the error is
logged and the order is still saved.

**29. Why is logic in services.py and not in views?**
So that every screen (customer, staff, agent, admin site, demo data) follows the same rules, and so
the rules can be tested directly without a browser.

## E. Security

**30. How are passwords stored?**
Never as plain text. Django stores a salted PBKDF2-SHA256 hash. Weak passwords (too short, common,
only numbers) are rejected.

**31. How do you make sure a staff member can't see another store's orders?**
Every view checks the role with `role_required`, and queries are filtered by the user's store.
Someone else's order returns 404, so we don't even reveal that it exists. Tests check this for
customers, staff and agents.

**32. What is CSRF and how is it handled?**
Cross-Site Request Forgery is when another website tricks your browser into submitting a form. Django
adds a secret token to every form and checks it on every POST. Logout is a POST too.

**33. How do you prevent SQL injection and XSS?**
The Django ORM uses parameterised queries; my raw SQL also passes values as parameters. Templates
auto-escape HTML, and text inside PDFs is escaped too.

**34. What validation do you do?**
Server-side validation on every form, even if the browser checks too:
- phone format and uniqueness
- pincode must have 6 digits
- quantities 0–50
- coupon rules
- slot in the future
- a stain must have a note
- photo must be an image of 5 MB or less

The database constraints are a second line of defence.

## F. Testing & deployment

**35. How did you test the project?**
138 automated Django tests on a real PostgreSQL test database, covering:
- order totals, coupons, slot capacity, status transitions and garment count mismatch
- the trigger and view, and the constraints
- every role's pages and their security

Plus manual testing in the browser. All 138 pass.

**36. Give an example of a bug your tests caught.**
Invoice lines showed prices including express, and then express was added again in the totals, so
the lines didn't add up. I fixed it, and now a test checks that the lines equal the subtotal.

**37. What is seed_demo?**
A management command that creates realistic Pune demo data: staff, agents, 20 customers and 60
orders in every status. It creates orders through the real business functions, so all rules and
history are genuine, and the same data appears on any computer.

**38. How would you deploy it for real?**
- On a Linux server: Gunicorn as the app server, Nginx in front with HTTPS, and PostgreSQL with daily backups.
- `DEBUG=False` and real SMTP settings in `.env`.
- Run `collectstatic`, and keep uploaded photos in `media/` or cloud storage.

## G. Wrap-up

**39. What are the limitations?**
Cash on Delivery only, email-only notifications, paper QR tags, no delivery time slots or route
planning, a single city in the demo, and no complaints or reviews module yet.

**40. What would you add next?**
Complaints/tickets and reviews, online UPI/card payment, SMS/WhatsApp alerts, an agent app with
in-app QR scanning, wash-proof RFID tags, GST invoices, and multi-city and Marathi/Hindi support.
