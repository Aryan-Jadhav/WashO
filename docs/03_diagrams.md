# WashO — System Diagrams

All diagrams are written in **Mermaid**, so they always match the text and can be edited like code.
They render automatically on GitHub and in VS Code (extension: *Markdown Preview Mermaid Support*).
To put one in the Word report, paste the code at <https://mermaid.live> and use **Actions → PNG**.

Contents:
1. [E-R diagram](#1-e-r-diagram)
2. [Data Flow Diagrams (Level 0, 1, 2)](#2-data-flow-diagrams)
3. [Use case diagram](#3-use-case-diagram)
4. [Class diagram](#4-class-diagram)
5. [Sequence diagrams (booking, tagging, delivery)](#5-sequence-diagrams)
6. [Activity diagram: order lifecycle](#6-activity-diagram-order-lifecycle)
7. [State diagram: order status](#7-state-diagram-order-status)
8. [Deployment diagram](#8-deployment-diagram)

---

## 1. E-R diagram

Main entities and their relationships. Crow's-foot notation: `||` exactly one, `o|` zero or one,
`|{` one or more, `o{` zero or more. Every table also has an `id` primary key.

```mermaid
erDiagram
    USER ||--o{ ADDRESS : "saves"
    USER }o--o{ GROUP : "has role"
    STORE o|--o{ USER : "employs (staff, agents)"
    CITY ||--o{ STORE : "has"
    STORE ||--|{ SERVICE_AREA : "serves"
    SERVICE_AREA ||--o{ ADDRESS : "located in"

    SERVICE_CATEGORY ||--o{ SERVICE_PRICE : "priced in"
    ITEM ||--o{ SERVICE_PRICE : "priced as"

    TIME_SLOT ||--o{ DAILY_SLOT : "booked as"
    SERVICE_AREA ||--o{ DAILY_SLOT : "for"
    DAILY_SLOT ||--o{ ORDER : "pickup in"

    USER ||--o{ ORDER : "places (customer)"
    USER o|--o{ ORDER : "picks up / delivers (agent)"
    ADDRESS ||--o{ ORDER : "pickup at"
    STORE ||--o{ ORDER : "processes"
    COUPON o|--o{ ORDER : "applied to"

    ORDER ||--|{ ORDER_ITEM : "estimate lines"
    ORDER ||--|{ ORDER_STATUS_HISTORY : "audit trail"
    ORDER ||--o{ GARMENT : "tagged as"
    ORDER ||--o{ COUNT_CHECK : "counted at"
    ORDER ||--o{ MISMATCH_ALERT : "raises"
    ORDER ||--o| PAYMENT : "paid by"

    SERVICE_CATEGORY ||--o{ ORDER_ITEM : ""
    ITEM ||--o{ ORDER_ITEM : ""
    SERVICE_CATEGORY ||--o{ GARMENT : ""
    ITEM ||--o{ GARMENT : ""
    USER ||--o{ PAYMENT : "collects (agent)"

    USER {
        string phone UK "10-digit mobile, login ID"
        string email "optional, unique if given"
        string first_name
        bigint store_id FK "staff and agents only"
    }
    ADDRESS {
        bigint user_id FK
        string line1
        bigint area_id FK
        bool is_default "one per user"
    }
    STORE {
        string name UK
        string pincode
        time opening_time
        time closing_time
    }
    SERVICE_AREA {
        string name
        string pincode
        bigint store_id FK
    }
    SERVICE_CATEGORY {
        string name UK
        bool express_available
        decimal express_surcharge_percent
    }
    ITEM {
        string name UK
        string group
        string unit
    }
    SERVICE_PRICE {
        bigint category_id FK
        bigint item_id FK
        decimal price "unique per category+item"
    }
    TIME_SLOT {
        time start_time
        time end_time
        int capacity "per area per day"
    }
    DAILY_SLOT {
        date date
        bigint time_slot_id FK
        bigint area_id FK
        int booked_count
    }
    COUPON {
        string code UK
        string discount_type
        decimal value
        decimal min_order_value
        date valid_until
    }
    ORDER {
        string code UK "WO-000123"
        string status
        bool is_express
        decimal subtotal
        decimal express_charge
        decimal discount
        decimal total "= subtotal + express - discount"
        bool bill_finalised
    }
    ORDER_ITEM {
        bigint order_id FK
        int quantity
        decimal unit_price "copied at booking"
    }
    ORDER_STATUS_HISTORY {
        bigint order_id FK
        string from_status
        string to_status
        bigint changed_by_id FK
        timestamp changed_at
    }
    GARMENT {
        string tag_code UK "WO-000123-01"
        bigint order_id FK
        bool has_stain
        bool has_damage
        string condition_note
        string photo
    }
    COUNT_CHECK {
        bigint order_id FK
        string checkpoint "pickup, store, delivery"
        int count
    }
    MISMATCH_ALERT {
        bigint order_id FK
        int expected_count
        int actual_count
        string status
    }
    PAYMENT {
        bigint order_id FK "one per order"
        string method "cash or upi"
        decimal amount
        bigint collected_by_id FK
    }
```

**Normalisation (3NF) in short:** every non-key column depends on the key, the whole key and nothing but the key.
- Prices live in `SERVICE_PRICE`, because a price depends on (category, item) together, not on either one alone.
- `SERVICE_AREA` has no city column; the city is found through its store.
- Pincode and city aren't repeated in `ADDRESS`; they come from the area.
- The only copies are **deliberate history snapshots**: `Order.address_snapshot`, and the prices in `OrderItem` and `Garment`. A bill must not change when the price list or a saved address changes later.

---

## 2. Data Flow Diagrams

### Level 0 — Context diagram

```mermaid
flowchart LR
    C([Customer])
    S([Store Staff])
    A([Delivery Agent])
    AD([Admin])
    P(("0<br/>WashO Laundry<br/>Management System"))

    C -- "registration, address, booking,<br/>coupon, cancel request" --> P
    P -- "estimate, order status, emails,<br/>garment list, PDF invoice" --> C
    S -- "receive order, garment details,<br/>stain/damage + photo, status updates" --> P
    P -- "order queue, QR tags, final bill,<br/>count warnings" --> S
    A -- "pickup count, delivery count,<br/>payment collected" --> P
    P -- "today's pickups & deliveries,<br/>amount to collect" --> A
    AD -- "master data, agent assignment,<br/>alert resolution" --> P
    P -- "dashboard, revenue report,<br/>mismatch alerts" --> AD
```

### Level 1 — Main processes

```mermaid
flowchart TB
    C([Customer]); S([Store Staff]); A([Delivery Agent]); AD([Admin])

    P1(("1.0<br/>Manage users<br/>& addresses"))
    P2(("2.0<br/>Book pickup"))
    P3(("3.0<br/>Assign agents<br/>& pickup"))
    P4(("4.0<br/>Tag garments<br/>& final bill"))
    P5(("5.0<br/>Clean &<br/>deliver"))
    P6(("6.0<br/>Collect payment<br/>& invoice"))
    P7(("7.0<br/>Reports &<br/>alerts"))

    D1[("D1 Users / Addresses")]
    D2[("D2 Catalog / Prices / Coupons")]
    D3[("D3 Slots")]
    D4[("D4 Orders / Status history")]
    D5[("D5 Garments / Counts / Alerts")]
    D6[("D6 Payments")]

    C -- details --> P1 --> D1
    C -- "items, date, slot, coupon" --> P2
    D1 --> P2
    D2 -- "prices, coupon rules" --> P2
    P2 <-- "reserve place" --> D3
    P2 -- "new order" --> D4
    P2 -- "estimate, email" --> C

    S -- "choose agent" --> P3
    A -- "pickup count" --> P3
    P3 --> D4
    P3 -- "pickup count" --> D5

    S -- "garments, stains, photos" --> P4
    P4 --> D5
    P4 -- "final bill, Tagged" --> D4
    P4 -- "mismatch?" --> P7

    S -- "cleaning, ready" --> P5
    A -- "delivery count" --> P5
    P5 --> D4
    P5 --> D5

    A -- "cash / UPI" --> P6 --> D6
    P6 -- "PDF invoice, email" --> C

    D4 --> P7
    D5 --> P7
    D6 -- "revenue view" --> P7
    P7 -- "dashboard, alerts" --> AD
    AD -- "resolve alert" --> P7
```

### Level 2 — Process 2.0 "Book pickup" and Process 4.0 "Tag garments"

```mermaid
flowchart TB
    C([Customer])
    subgraph P2["2.0 Book pickup"]
        P21(("2.1<br/>Select address<br/>(served area only)"))
        P22(("2.2<br/>Enter item<br/>counts"))
        P23(("2.3<br/>Calculate estimate<br/>+ express + coupon"))
        P24(("2.4<br/>Show free<br/>slots"))
        P25(("2.5<br/>Reserve slot &<br/>save order<br/>(one transaction)"))
    end
    D1[("D1 Addresses")]; D2[("D2 Prices / Coupons")]; D3[("D3 Daily slots")]; D4[("D4 Orders")]

    C --> P21
    D1 --> P21
    C --> P22 --> P23
    D2 --> P23
    P23 -- "live estimate" --> C
    P21 -- "area" --> P24
    D3 -- "places left" --> P24 -- "slot buttons" --> C
    C -- "confirm" --> P25
    P25 -- "lock row, +1" --> D3
    P25 -- "order + items (trigger writes history)" --> D4
```

```mermaid
flowchart TB
    S([Store Staff]); AD([Admin])
    subgraph P4["4.0 Tag garments & final bill"]
        P41(("4.1<br/>Add garment:<br/>item, stain, photo"))
        P42(("4.2<br/>Generate tag code<br/>+ QR"))
        P43(("4.3<br/>Compare store count<br/>with pickup count"))
        P44(("4.4<br/>Make final bill<br/>from garments"))
        P45(("4.5<br/>Raise mismatch<br/>alert + email"))
    end
    D4[("D4 Orders")]; D5[("D5 Garments / Counts")]; D7[("D7 Alerts")]

    S --> P41 --> P42 --> D5
    P42 -- "QR labels" --> S
    S -- "finish tagging" --> P43
    D5 -- "pickup count" --> P43
    P43 -- "equal" --> P44
    P43 -- "different (staff confirmed)" --> P45 --> D7
    P45 -- "email" --> AD
    P45 --> P44
    P44 -- "subtotal, express, discount, total" --> D4
```

---

## 3. Use case diagram

Mermaid has no native use case diagram, so each actor is drawn on the left with its use cases grouped
inside the system boundary. **Login** is included in every use case except the public ones, and
**Admin** can also do everything Store Staff can, for all stores.

```mermaid
flowchart LR
    Visitor(["👤 Visitor"])
    Customer(["👤 Customer"])
    Staff(["👤 Store Staff"])
    Agent(["👤 Delivery Agent"])
    Admin(["👤 Admin"])

    subgraph WashO["WashO system"]
        direction TB
        subgraph ADM["Admin"]
            UC16([View dashboard & revenue])
            UC17([Resolve mismatch alerts])
            UC18([Manage master data])
        end
        subgraph AGT["Delivery Agent"]
            UC14([Confirm pickup with count])
            UC15([Confirm delivery, collect cash/UPI])
        end
        subgraph STF["Store Staff"]
            UC9([Assign pickup / delivery agent])
            UC10([Receive order at store])
            UC11([Tag garments: QR, stain, photo])
            UC12([Finish tagging → final bill])
            UC13([Update cleaning status])
        end
        subgraph CUS["Customer"]
            UC4([Manage addresses])
            UC5([Book pickup with coupon])
            UC6([Track live order status])
            UC7([Cancel before pickup])
            UC8([Download PDF invoice])
        end
        subgraph PUB["Public"]
            UC1([View services, price list, stores, FAQ])
            UC2([Check pincode / contact us])
            UC3([Register / Login])
        end
    end

    Visitor --- PUB
    Customer --- CUS
    Staff --- STF
    Agent --- AGT
    Admin --- ADM
```
---

## 4. Class diagram

Main model classes (fields abbreviated) and the service functions that hold the business rules.

```mermaid
classDiagram
    direction LR
    class User {
        +phone: str
        +email: str
        +store: Store
        +has_role(*roles) bool
        +role: str
    }
    class Address {
        +label: str
        +line1: str
        +area: ServiceArea
        +is_default: bool
        +one_line() str
    }
    class Store {
        +name: str
        +pincode: str
        +map_url: str
    }
    class ServiceArea {
        +name: str
        +pincode: str
    }
    class ServiceCategory {
        +name: str
        +express_available: bool
        +express_surcharge_percent: Decimal
    }
    class Item {
        +name: str
        +group: str
        +unit: str
    }
    class ServicePrice {
        +price: Decimal
        +unit_price(express) Decimal
        +express_price: Decimal
    }
    class TimeSlot {
        +start_time: time
        +end_time: time
        +capacity: int
    }
    class DailySlot {
        +date: date
        +booked_count: int
    }
    class Coupon {
        +code: str
        +discount_type: str
        +value: Decimal
        +check_usable(user, amount, today)
        +discount_for(amount) Decimal
    }
    class Order {
        +code: str
        +status: OrderStatus
        +is_express: bool
        +subtotal: Decimal
        +express_charge: Decimal
        +discount: Decimal
        +total: Decimal
        +bill_finalised: bool
        +is_open: bool
        +can_cancel: bool
    }
    class OrderItem {
        +quantity: int
        +unit_price: Decimal
        +line_total: Decimal
    }
    class OrderStatusHistory {
        +from_status: str
        +to_status: str
        +changed_at: datetime
    }
    class Garment {
        +tag_code: str
        +has_stain: bool
        +has_damage: bool
        +condition_note: str
        +photo: Image
    }
    class CountCheck {
        +checkpoint: str
        +count: int
    }
    class MismatchAlert {
        +expected_count: int
        +actual_count: int
        +status: str
        +difference: int
    }
    class Payment {
        +method: str
        +amount: Decimal
        +collected_at: datetime
    }
    class OrderServices {
        <<module orders.services>>
        +create_order(...) Order
        +change_status(order, status, by) Order
        +cancel_order(order, by)
        +reserve_slot(date, slot, area) DailySlot
    }
    class TaggingServices {
        <<module tagging.services>>
        +add_garment(order, price, by, ...) Garment
        +record_count(order, checkpoint, count, by)
        +finish_tagging(order, by, confirm)
        +finalise_bill(order)
    }
    class DeliveryServices {
        <<module delivery.services>>
        +assign_pickup_agent(order, agent, by)
        +confirm_pickup(order, agent, count)
        +confirm_delivery(order, agent, count, payment)
    }

    User "1" --> "*" Address
    Store "1" --> "*" ServiceArea
    ServiceArea "1" --> "*" Address
    ServiceCategory "1" --> "*" ServicePrice
    Item "1" --> "*" ServicePrice
    TimeSlot "1" --> "*" DailySlot
    DailySlot "1" --> "*" Order
    User "1" --> "*" Order : customer
    Coupon "0..1" --> "*" Order
    Order "1" *-- "*" OrderItem
    Order "1" *-- "*" OrderStatusHistory
    Order "1" --> "*" Garment
    Order "1" *-- "*" CountCheck
    Order "1" *-- "*" MismatchAlert
    Order "1" --> "0..1" Payment
    OrderServices ..> Order : changes
    TaggingServices ..> Garment : creates
    TaggingServices ..> MismatchAlert : raises
    DeliveryServices ..> Payment : records
```

---

## 5. Sequence diagrams

### 5.1 Booking a pickup

```mermaid
sequenceDiagram
    autonumber
    actor C as Customer
    participant B as Browser (HTMX)
    participant V as Django view
    participant SV as orders.services
    participant DB as PostgreSQL

    C->>B: Opens "Book pickup"
    B->>V: GET /orders/book/
    V->>DB: addresses, prices, slot availability
    V-->>B: Booking page
    C->>B: Types item counts / coupon
    B->>V: POST /orders/book/estimate/ (HTMX)
    V-->>B: Updated estimate box (no reload)
    C->>B: Picks date
    B->>V: GET /orders/book/slots/ (HTMX)
    V-->>B: Slot buttons with "N left"
    C->>B: Confirm pickup
    B->>V: POST /orders/book/ (CSRF token)
    V->>V: Validate form (server side)
    V->>SV: create_order(...)
    SV->>DB: BEGIN
    SV->>DB: SELECT daily slot FOR UPDATE (row lock)
    alt slot full
        SV-->>V: BookingError "slot just got full"
        SV->>DB: ROLLBACK
    else place available
        SV->>DB: booked_count + 1
        SV->>DB: check coupon (locked)
        SV->>DB: INSERT order + items
        DB->>DB: TRIGGER writes history "Booked"
        SV->>DB: COMMIT
        SV-->>V: Order WO-000123
        V-->>B: Redirect to order page
        Note over SV: on commit → "Pickup booked" email
    end
```

### 5.2 Garment tagging at the store

```mermaid
sequenceDiagram
    autonumber
    actor ST as Store Staff
    participant B as Browser (HTMX)
    participant V as Staff panel view
    participant TS as tagging.services
    participant DB as PostgreSQL
    actor AD as Admin

    ST->>B: Mark received at store
    B->>V: POST step → change_status(At Store)
    loop for every garment
        ST->>B: Choose item, stain/damage note, photo
        B->>V: POST garment_add (HTMX, multipart)
        V->>TS: add_garment(order, price, ...)
        TS->>DB: lock order, next seq, INSERT garment WO-000123-NN
        V-->>B: New row with QR code (no page reload)
    end
    ST->>B: Finish tagging
    B->>V: POST finish_tagging
    V->>TS: finish_tagging(order, confirm)
    TS->>DB: pickup count?
    alt counts differ and not confirmed
        TS-->>V: "Re-check the bag, then tick confirmation"
    else counts equal or confirmed
        TS->>DB: record store count
        opt store count ≠ pickup count
            TS->>DB: INSERT mismatch alert
            TS-->>AD: email (after commit)
        end
        TS->>DB: final bill = sum of garment prices + express - coupon
        TS->>DB: status → Tagged (trigger logs it)
        V-->>B: "Final bill ₹…"
    end
```

### 5.3 Delivery with Cash on Delivery

```mermaid
sequenceDiagram
    autonumber
    actor ST as Store Staff
    actor AG as Delivery Agent
    participant V as Agent panel
    participant DS as delivery.services
    participant DB as PostgreSQL
    actor C as Customer

    ST->>V: Assign delivery agent + date (order Ready)
    AG->>V: Open "My jobs" (today)
    AG->>V: "Collected. Start delivery"
    V->>DS: start_delivery → Out for Delivery
    DS-->>C: email "please keep ₹… ready"
    AG->>C: Hands over clothes, counts together
    AG->>V: Count + Cash/UPI + "I have collected ₹…"
    V->>DS: confirm_delivery(count, payment)
    DS->>DB: BEGIN
    DS->>DB: compare with store count
    alt different and not confirmed
        DS-->>V: "Count again with the customer"
        DS->>DB: ROLLBACK
    else ok
        DS->>DB: record delivery count (+ alert if different)
        DS->>DB: INSERT payment (amount = final bill)
        DS->>DB: status → Delivered (trigger logs it)
        DS->>DB: COMMIT
        DS-->>C: email "Delivered" + PDF invoice attached
    end
```

---

## 6. Activity diagram: order lifecycle

```mermaid
flowchart TD
    start((●)) --> book[Customer books pickup<br/>estimate shown]
    book --> slot{Slot place<br/>available?}
    slot -- no --> pick[Choose another slot] --> book
    slot -- yes --> booked[Status: Booked]
    booked --> cancel1{Customer<br/>cancels?}
    cancel1 -- yes --> cancelled[Status: Cancelled<br/>slot place released]
    cancel1 -- no --> assign[Staff assigns pickup agent<br/>Status: Pickup Assigned]
    assign --> cancel2{Customer<br/>cancels?}
    cancel2 -- yes --> cancelled
    cancel2 -- no --> pickup[Agent counts garments with customer<br/>Status: Picked Up]
    pickup --> atstore[Staff receives bag<br/>Status: At Store]
    atstore --> tag[Tag each garment: QR, stain/damage, photo]
    tag --> more{More<br/>garments?}
    more -- yes --> tag
    more -- no --> cmp1{Tagged count =<br/>pickup count?}
    cmp1 -- no --> alert1[Re-check, confirm<br/>Mismatch alert to admin]
    alert1 --> bill
    cmp1 -- yes --> bill[Final bill from garments<br/>Status: Tagged]
    bill --> clean[Status: In Cleaning]
    clean --> ready[Status: Ready]
    ready --> dagent[Staff assigns delivery agent]
    dagent --> out[Status: Out for Delivery]
    out --> cmp2{Delivered count =<br/>store count?}
    cmp2 -- no --> alert2[Recount, confirm<br/>Mismatch alert to admin]
    alert2 --> pay
    cmp2 -- yes --> pay[Collect cash / UPI]
    pay --> delivered[Status: Delivered<br/>invoice emailed]
    delivered --> stop((◉))
    cancelled --> stop
```

---

## 7. State diagram: order status

Exactly the transitions allowed by `ALLOWED_TRANSITIONS` in `orders/services.py`. Anything else is rejected.

```mermaid
stateDiagram-v2
    [*] --> Booked : customer books
    Booked --> PickupAssigned : staff assigns agent
    Booked --> Cancelled : customer / admin cancels
    PickupAssigned --> PickedUp : agent confirms count
    PickupAssigned --> Cancelled : cancel before pickup
    PickedUp --> AtStore : staff receives
    AtStore --> Tagged : tagging finished (final bill)
    Tagged --> InCleaning
    InCleaning --> Ready
    Ready --> OutForDelivery : agent collects (needs delivery agent)
    OutForDelivery --> Delivered : count + payment
    Delivered --> [*]
    Cancelled --> [*]

    PickupAssigned : Pickup Assigned
    PickedUp : Picked Up
    AtStore : At Store
    InCleaning : In Cleaning
    OutForDelivery : Out for Delivery
```

---

## 8. Deployment diagram

How the system runs on the project laptop (development). For a real launch, the same code runs behind
Gunicorn/Nginx on a Linux server; only the settings in `.env` change.

```mermaid
flowchart LR
    subgraph Client["Client devices"]
        PC["💻 Browser on PC<br/>Customer / Staff / Admin"]
        Phone["📱 Phone browser<br/>Delivery Agent, camera for photos"]
    end

    subgraph Laptop["Windows laptop (start.bat)"]
        direction TB
        subgraph Django["Python 3.14 · Django 5.2 LTS (runserver :8000)"]
            Apps["Apps: core, accounts, stores, catalog,<br/>orders, tagging, delivery, payments, dashboard"]
            Static["Static files: CSS, logo"]
            Media["media/ : garment photos"]
        end
        PG[("PostgreSQL 18<br/>database 'washo'<br/>trigger + view")]
        Env[".env settings<br/>(DB password, SECRET_KEY)"]
    end

    CDN["CDN (jsDelivr):<br/>Bootstrap 5, Bootstrap Icons,<br/>HTMX, Chart.js"]
    Mail["Email: console now /<br/>SMTP server later"]

    PC -- "HTTP" --> Django
    Phone -- "HTTP (same Wi-Fi)" --> Django
    Django -- "psycopg 3 (TCP 5432)" --> PG
    Env -.-> Django
    PC -. "loads JS/CSS" .-> CDN
    Phone -.-> CDN
    Django -- "emails" --> Mail
```
