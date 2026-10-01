# Data Dictionary

Generated from the Django models by `scripts/gen_data_dictionary.py` (do not edit by hand).
Every table has an auto-increment primary key `id` (bigint) unless shown otherwise.
Types are the PostgreSQL column types. FK rules: CASCADE = delete children too, PROTECT = refuse to delete while referenced, SET_NULL = keep the row and clear the link.

## Tables

1. [`accounts_user`](#accountsuser) — User
2. [`accounts_address`](#accountsaddress) — Address
3. [`stores_city`](#storescity) — City
4. [`stores_store`](#storesstore) — Store
5. [`stores_servicearea`](#storesservicearea) — Service Area
6. [`catalog_servicecategory`](#catalogservicecategory) — Service Category
7. [`catalog_item`](#catalogitem) — Item
8. [`catalog_serviceprice`](#catalogserviceprice) — Service Price
9. [`orders_timeslot`](#orderstimeslot) — Time Slot
10. [`orders_dailyslot`](#ordersdailyslot) — Daily Slot
11. [`orders_coupon`](#orderscoupon) — Coupon
12. [`orders_order`](#ordersorder) — Order
13. [`orders_orderitem`](#ordersorderitem) — Order Item
14. [`orders_orderstatushistory`](#ordersorderstatushistory) — Order Status History
15. [`tagging_garment`](#tagginggarment) — Garment
16. [`tagging_countcheck`](#taggingcountcheck) — Count Check
17. [`tagging_mismatchalert`](#taggingmismatchalert) — Mismatch Alert
18. [`payments_payment`](#paymentspayment) — Payment
19. [`dashboard_daily_revenue`](#dashboarddailyrevenue) — Daily Revenue
20. [`core_contactmessage`](#corecontactmessage) — Contact Message
21. [`core_faq`](#corefaq) — Faq
22. [`auth_group`](#authgroup) — Group

### `accounts_user` — User

Custom user: logs in with mobile number; email is optional.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `password` | varchar(128) | NOT NULL | Password |
| `last_login` | timestamp with time zone | NULL | Last login |
| `is_superuser` | boolean | NOT NULL; DEFAULT False | Designates that this user has all permissions without explicitly assigning them. |
| `first_name` | varchar(150) | NOT NULL | First name |
| `last_name` | varchar(150) | NOT NULL | Last name |
| `is_staff` | boolean | NOT NULL; DEFAULT False | Designates whether the user can log into this admin site. |
| `is_active` | boolean | NOT NULL; DEFAULT True | Designates whether this user should be treated as active. Unselect this instead of deleting accounts. |
| `date_joined` | timestamp with time zone | NOT NULL | Date joined |
| `phone` | varchar(10) | UNIQUE; NOT NULL | 10-digit mobile number, used to log in. |
| `email` | varchar(254) | NOT NULL | Email address |
| `store_id` | bigint | FK → stores_store (PROTECT); NULL | Only for Store Staff and Delivery Agents. |
| `groups` | (link table `accounts_user_groups`) | M2M → auth_group | The groups this user belongs to. A user will get all permissions granted to each of their groups. |
| `user_permissions` | (link table `accounts_user_user_permissions`) | M2M → auth_permission | Specific permissions for this user. |

Table-level constraints and indexes:

- **UNIQUE** `unique_email_when_present`: (email) WHERE NOT email = ''
- **CHECK** `phone_is_valid_indian_mobile`: phone matches regex '^[6-9]\d{9}$'

### `accounts_address` — Address

A customer's saved pickup/delivery address.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `user_id` | bigint | FK → accounts_user (CASCADE); NOT NULL | User |
| `label` | varchar(10) | NOT NULL; DEFAULT Address.Label.HOME; CHOICES: home, work, other | Label |
| `line1` | varchar(150) | NOT NULL | Flat / house no., building |
| `line2` | varchar(150) | NOT NULL | Street / landmark |
| `area_id` | bigint | FK → stores_servicearea (PROTECT); NOT NULL | Locality |
| `is_default` | boolean | NOT NULL; DEFAULT False | Is default |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |
| `created_at` | timestamp with time zone | NOT NULL | Created at |

Table-level constraints and indexes:

- **UNIQUE** `one_default_address_per_user`: (user) WHERE (is_active = True AND is_default = True)

### `stores_city` — City

Stores cities.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `name` | varchar(60) | UNIQUE; NOT NULL | Name |
| `slug` | varchar(60) | UNIQUE; NOT NULL | Slug |
| `state` | varchar(60) | NOT NULL; DEFAULT 'Maharashtra' | State |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

### `stores_store` — Store

A physical WashO store where clothes are tagged and cleaned.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `name` | varchar(100) | UNIQUE; NOT NULL | Name |
| `slug` | varchar(100) | UNIQUE; NOT NULL | Slug |
| `city_id` | bigint | FK → stores_city (PROTECT); NOT NULL | City |
| `address` | varchar(255) | NOT NULL | Address |
| `locality` | varchar(100) | NOT NULL | Area where the store is, e.g. Kothrud. |
| `pincode` | varchar(6) | NOT NULL; INDEX | Pincode |
| `phone` | varchar(15) | NOT NULL | Phone |
| `email` | varchar(254) | NOT NULL | Email |
| `opening_time` | time | NOT NULL | Opening time |
| `closing_time` | time | NOT NULL | Closing time |
| `latitude` | numeric(9, 6) | NULL | Latitude |
| `longitude` | numeric(9, 6) | NULL | Longitude |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

Table-level constraints and indexes:

- **CHECK** `store_closes_after_opening`: closing_time > opening_time

### `stores_servicearea` — Service Area

A locality + pincode where we pick up and deliver, served by one store.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `name` | varchar(100) | NOT NULL | Locality |
| `pincode` | varchar(6) | NOT NULL; INDEX | Pincode |
| `store_id` | bigint | FK → stores_store (PROTECT); NOT NULL | Store |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

Table-level constraints and indexes:

- **UNIQUE** `unique_area_name_pincode`: (name, pincode)

### `catalog_servicecategory` — Service Category

A type of service, e.g. Dry Clean or Wash & Iron.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `name` | varchar(60) | UNIQUE; NOT NULL | Name |
| `slug` | varchar(60) | UNIQUE; NOT NULL | Used in web addresses, e.g. dry-clean. |
| `description` | text | NOT NULL | Description |
| `icon` | varchar(40) | NOT NULL; DEFAULT 'basket' | Bootstrap Icons name, e.g. 'stars'. |
| `standard_turnaround_hours` | smallint | NOT NULL; DEFAULT 48 | Standard turnaround hours |
| `express_available` | boolean | NOT NULL; DEFAULT False | Express available |
| `express_surcharge_percent` | numeric(5, 2) | NOT NULL; DEFAULT Decimal('0') | Extra % added to the price when the customer chooses Express. |
| `express_turnaround_hours` | smallint | NULL | Express turnaround hours |
| `sort_order` | smallint | NOT NULL; DEFAULT 0 | Sort order |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

Table-level constraints and indexes:

- **CHECK** `category_surcharge_0_to_100`: (express_surcharge_percent >= 0 AND express_surcharge_percent <= 100)
- **CHECK** `category_express_needs_surcharge_and_time`: (express_available = False OR (express_surcharge_percent > 0 AND express_turnaround_hours IS NOT NULL))

### `catalog_item` — Item

A garment or article, e.g. Shirt, Saree, Blanket, Sports Shoes.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `name` | varchar(80) | UNIQUE; NOT NULL | Name |
| `group` | varchar(20) | NOT NULL; INDEX; CHOICES: men, women, kids, household, footwear, accessories | Group |
| `unit` | varchar(10) | NOT NULL; DEFAULT Item.Unit.PIECE; CHOICES: piece, pair, set | Unit |
| `sort_order` | smallint | NOT NULL; DEFAULT 0 | Sort order |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

### `catalog_serviceprice` — Service Price

Price of one item in one service category (e.g. Dry Clean + Saree = ₹299).

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `category_id` | bigint | FK → catalog_servicecategory (PROTECT); NOT NULL | Category |
| `item_id` | bigint | FK → catalog_item (PROTECT); NOT NULL | Item |
| `price` | numeric(8, 2) | NOT NULL | Price |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

Table-level constraints and indexes:

- **UNIQUE** `unique_price_per_category_item`: (category, item)
- **CHECK** `price_positive`: price > 0

### `orders_timeslot` — Time Slot

A pickup window such as 10:00–12:00, offered every day.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `start_time` | time | NOT NULL | Start time |
| `end_time` | time | NOT NULL | End time |
| `capacity` | smallint | NOT NULL; DEFAULT 5 | Capacity |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

Table-level constraints and indexes:

- **UNIQUE** `unique_time_slot`: (start_time, end_time)
- **CHECK** `slot_ends_after_start`: end_time > start_time
- **CHECK** `slot_capacity_at_least_1`: capacity >= 1

### `orders_dailyslot` — Daily Slot

How many pickups are booked for one slot, on one date, in one area.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `date` | date | NOT NULL | Date |
| `time_slot_id` | bigint | FK → orders_timeslot (PROTECT); NOT NULL | Time slot |
| `area_id` | bigint | FK → stores_servicearea (PROTECT); NOT NULL | Area |
| `booked_count` | smallint | NOT NULL; DEFAULT 0 | Booked count |

Table-level constraints and indexes:

- **UNIQUE** `unique_daily_slot`: (date, time_slot, area)
- **CHECK** `daily_slot_count_not_negative`: booked_count >= 0
- **INDEX** `orders_dail_date_f9af66_idx`: (date, area)

### `orders_coupon` — Coupon

Stores coupons.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `code` | varchar(20) | UNIQUE; NOT NULL | Customers type this. Stored in CAPITALS. |
| `description` | varchar(200) | NOT NULL | Description |
| `discount_type` | varchar(10) | NOT NULL; CHOICES: flat, percent | Discount type |
| `value` | numeric(8, 2) | NOT NULL | ₹ amount or % depending on type. |
| `max_discount` | numeric(8, 2) | NULL | Upper limit for percentage coupons (optional). |
| `min_order_value` | numeric(8, 2) | NOT NULL; DEFAULT Decimal('0') | Min order value |
| `valid_from` | date | NOT NULL | Valid from |
| `valid_until` | date | NOT NULL | Valid until |
| `usage_limit` | integer | NULL | Total uses allowed. Empty = unlimited. |
| `per_user_limit` | smallint | NOT NULL; DEFAULT 1 | Uses per customer. 0 = unlimited. |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

Table-level constraints and indexes:

- **CHECK** `coupon_value_positive`: value > 0
- **CHECK** `coupon_percent_max_100`: (discount_type = 'flat' OR value <= 100)
- **CHECK** `coupon_dates_in_order`: valid_until >= valid_from
- **CHECK** `coupon_code_uppercase`: code = UPPER(code)

### `orders_order` — Order

Stores orders.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `code` | varchar(12) | UNIQUE; NULL | Order number shown to customers. |
| `customer_id` | bigint | FK → accounts_user (PROTECT); NOT NULL | Customer |
| `address_id` | bigint | FK → accounts_address (PROTECT); NOT NULL | Address |
| `address_snapshot` | text | NOT NULL | Address snapshot |
| `store_id` | bigint | FK → stores_store (PROTECT); NOT NULL | Store |
| `pickup_slot_id` | bigint | FK → orders_dailyslot (PROTECT); NOT NULL | Pickup slot |
| `is_express` | boolean | NOT NULL; DEFAULT False | Is express |
| `status` | varchar(20) | NOT NULL; DEFAULT OrderStatus.BOOKED; INDEX; CHOICES: booked, pickup_assigned, picked_up, at_store, tagged, in_cleaning, ready, out_for_delivery, delivered, cancelled | Status |
| `coupon_id` | bigint | FK → orders_coupon (PROTECT); NULL | Coupon |
| `estimated_total` | numeric(10, 2) | NOT NULL | Estimated total |
| `subtotal` | numeric(10, 2) | NOT NULL | Subtotal |
| `express_charge` | numeric(10, 2) | NOT NULL; DEFAULT Decimal('0') | Express charge |
| `discount` | numeric(10, 2) | NOT NULL; DEFAULT Decimal('0') | Discount |
| `total` | numeric(10, 2) | NOT NULL | Total |
| `bill_finalised` | boolean | NOT NULL; DEFAULT False | Bill finalised |
| `pickup_agent_id` | bigint | FK → accounts_user (SET_NULL); NULL | Pickup agent |
| `delivery_agent_id` | bigint | FK → accounts_user (SET_NULL); NULL | Delivery agent |
| `delivery_date` | date | NULL | Delivery date |
| `customer_note` | varchar(300) | NOT NULL | Customer note |
| `created_at` | timestamp with time zone | NOT NULL; INDEX | Created at |
| `updated_at` | timestamp with time zone | NOT NULL | Updated at |

Table-level constraints and indexes:

- **CHECK** `order_status_valid`: status IN ('booked', 'pickup_assigned', 'picked_up', 'at_store', 'tagged', 'in_cleaning', 'ready', 'out_for_delivery', 'delivered', 'cancelled')
- **CHECK** `order_amounts_not_negative`: (discount >= 0 AND express_charge >= 0 AND subtotal >= 0 AND total >= 0)
- **CHECK** `order_total_adds_up`: total = subtotal + express_charge - discount
- **INDEX** `orders_orde_custome_413d7d_idx`: (customer, -created_at)
- **INDEX** `orders_orde_pickup__7cb5b7_idx`: (pickup_agent, status)
- **INDEX** `orders_orde_deliver_000e33_idx`: (delivery_agent, status)

### `orders_orderitem` — Order Item

One line of the booking estimate, e.g. 'Wash & Iron – Shirt × 5'.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `order_id` | bigint | FK → orders_order (CASCADE); NOT NULL | Order |
| `category_id` | bigint | FK → catalog_servicecategory (PROTECT); NOT NULL | Category |
| `item_id` | bigint | FK → catalog_item (PROTECT); NOT NULL | Item |
| `quantity` | smallint | NOT NULL | Quantity |
| `unit_price` | numeric(8, 2) | NOT NULL | Unit price |
| `express_surcharge` | numeric(8, 2) | NOT NULL; DEFAULT Decimal('0') | Extra per unit for Express. |

Table-level constraints and indexes:

- **UNIQUE** `unique_item_per_order`: (order, category, item)
- **CHECK** `order_item_quantity_positive`: quantity >= 1

### `orders_orderstatushistory` — Order Status History

Audit trail: every status change with time and the user who made it.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `order_id` | bigint | FK → orders_order (CASCADE); NOT NULL | Order |
| `from_status` | varchar(20) | NOT NULL | From status |
| `to_status` | varchar(20) | NOT NULL | To status |
| `changed_by_id` | bigint | FK → accounts_user (SET_NULL); NULL | Changed by |
| `note` | varchar(300) | NOT NULL; DB DEFAULT | Note |
| `changed_at` | timestamp with time zone | NOT NULL; DB DEFAULT | Changed at |

Table-level constraints and indexes:

- **INDEX** `orders_orde_order_i_7978aa_idx`: (order, changed_at)

### `tagging_garment` — Garment

ONE physical garment, tagged at the store with its own code + QR.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `order_id` | bigint | FK → orders_order (PROTECT); NOT NULL | Order |
| `seq` | smallint | NOT NULL | 1, 2, 3 ... within the order. |
| `tag_code` | varchar(20) | UNIQUE; NOT NULL | Printed on the tag, e.g. WO-000012-03. |
| `category_id` | bigint | FK → catalog_servicecategory (PROTECT); NOT NULL | Category |
| `item_id` | bigint | FK → catalog_item (PROTECT); NOT NULL | Item |
| `unit_price` | numeric(8, 2) | NOT NULL | Unit price |
| `express_surcharge` | numeric(8, 2) | NOT NULL; DEFAULT 0 | Express surcharge |
| `description` | varchar(120) | NOT NULL | Colour / brand, e.g. 'Blue, Raymond'. |
| `has_stain` | boolean | NOT NULL; DEFAULT False | Has stain |
| `has_damage` | boolean | NOT NULL; DEFAULT False | Has damage |
| `condition_note` | varchar(300) | NOT NULL | Where and what, e.g. 'Oil stain on left sleeve'. |
| `photo` | varchar(100) | NOT NULL | Photo |
| `tagged_by_id` | bigint | FK → accounts_user (SET_NULL); NULL | Tagged by |
| `tagged_at` | timestamp with time zone | NOT NULL | Tagged at |

Table-level constraints and indexes:

- **UNIQUE** `unique_garment_seq_per_order`: (order, seq)
- **CHECK** `garment_issue_needs_note`: ((has_damage = False AND has_stain = False) OR NOT condition_note = '')

### `tagging_countcheck` — Count Check

How many garments were counted at one checkpoint of an order.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `order_id` | bigint | FK → orders_order (CASCADE); NOT NULL | Order |
| `checkpoint` | varchar(10) | NOT NULL; CHOICES: pickup, store, delivery | Checkpoint |
| `count` | smallint | NOT NULL | Count |
| `recorded_by_id` | bigint | FK → accounts_user (SET_NULL); NULL | Recorded by |
| `recorded_at` | timestamp with time zone | NOT NULL | Recorded at |
| `note` | varchar(200) | NOT NULL | Note |

Table-level constraints and indexes:

- **UNIQUE** `one_count_per_checkpoint`: (order, checkpoint)

### `tagging_mismatchalert` — Mismatch Alert

Raised automatically when a count differs from the previous checkpoint.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `order_id` | bigint | FK → orders_order (CASCADE); NOT NULL | Order |
| `checkpoint` | varchar(10) | NOT NULL; CHOICES: pickup, store, delivery | Where the difference was found. |
| `expected_count` | smallint | NOT NULL | Count at the previous checkpoint. |
| `actual_count` | smallint | NOT NULL | Actual count |
| `status` | varchar(10) | NOT NULL; DEFAULT MismatchAlert.Status.OPEN; INDEX; CHOICES: open, resolved | Status |
| `created_at` | timestamp with time zone | NOT NULL | Created at |
| `resolved_by_id` | bigint | FK → accounts_user (SET_NULL); NULL | Resolved by |
| `resolved_at` | timestamp with time zone | NULL | Resolved at |
| `resolution_note` | varchar(300) | NOT NULL | Resolution note |

Table-level constraints and indexes:

- **CHECK** `alert_only_when_counts_differ`: NOT expected_count = actual_count
- **CHECK** `resolved_alert_has_time`: (status = 'open' OR resolved_at IS NOT NULL)

### `payments_payment` — Payment

Money collected for an order. WashO uses Cash on Delivery: the agent collects the final bill at the door, in cash or by UPI to the store's QR.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `order_id` | bigint | FK → orders_order (PROTECT); UNIQUE; NOT NULL | Order |
| `method` | varchar(10) | NOT NULL; CHOICES: cash, upi | Method |
| `amount` | numeric(10, 2) | NOT NULL | Amount |
| `collected_by_id` | bigint | FK → accounts_user (PROTECT); NOT NULL | Collected by |
| `collected_at` | timestamp with time zone | NOT NULL; INDEX | Collected at |
| `reference` | varchar(40) | NOT NULL | UPI transaction ID (optional). |

Table-level constraints and indexes:

- **CHECK** `payment_amount_positive`: amount > 0
- **INDEX** `payments_pa_collect_5347d5_idx`: (collected_by, collected_at)

### `dashboard_daily_revenue` — Daily Revenue

Read-only model over the PostgreSQL VIEW `dashboard_daily_revenue` (see migration 0001).

*Read-only: this is a **PostgreSQL VIEW**, not a table.*

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `day` | date | NOT NULL | Day |
| `store_id` | bigint | FK → stores_store (DO_NOTHING); NOT NULL | Store |
| `orders` | integer | NOT NULL | Orders |
| `revenue` | numeric(12, 2) | NOT NULL | Revenue |

### `core_contactmessage` — Contact Message

A message sent from the public Contact page (anyone, no login needed).

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `name` | varchar(100) | NOT NULL | Name |
| `phone` | varchar(10) | NOT NULL | Mobile number |
| `email` | varchar(254) | NOT NULL | Email |
| `subject` | varchar(150) | NOT NULL | Subject |
| `message` | text | NOT NULL | Message |
| `is_resolved` | boolean | NOT NULL; DEFAULT False | Is resolved |
| `created_at` | timestamp with time zone | NOT NULL | Created at |

Table-level constraints and indexes:

- **INDEX** `core_contac_is_reso_0d7b86_idx`: (is_resolved, created_at)

### `core_faq` — Faq

FAQ entries are stored in the DB so the admin can edit them without code changes.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | bigint | PK; NOT NULL | Id |
| `question` | varchar(255) | NOT NULL | Question |
| `answer` | text | NOT NULL | Answer |
| `sort_order` | smallint | NOT NULL; DEFAULT 0 | Smaller numbers show first. |
| `is_active` | boolean | NOT NULL; DEFAULT True | Is active |

### `auth_group` — Group

Groups are a generic way of categorizing users to apply permissions, or some other label, to those users. A user can belong to any number of groups.

| Field | Type | Constraint | Description |
|---|---|---|---|
| `id` | integer | PK; NOT NULL | Id |
| `name` | varchar(150) | UNIQUE; NOT NULL | Name |
| `permissions` | (link table `auth_group_permissions`) | M2M → auth_permission | Permissions |

## PostgreSQL trigger

| Object | Type | Fires | Action |
|---|---|---|---|
| `washo_log_order_status()` | PL/pgSQL function | — | Inserts a row in `orders_orderstatushistory` (old status, new status, user from setting `washo.changed_by`, note, time). |
| `trg_order_status_on_insert` | AFTER INSERT trigger on `orders_order` | every new order | calls the function (history starts with Booked) |
| `trg_order_status_on_update` | AFTER UPDATE OF status trigger on `orders_order` | only when status really changes | calls the function |
