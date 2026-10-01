# WashO — Online Laundry & Dry-Cleaning Platform

T.Y. B.Sc. Computer Science final-year project (Savitribai Phule Pune University, NEP 2020).

Customers book a doorstep pickup. A delivery agent collects the clothes, store staff tag **every
garment** with its own QR code, and the clothes are cleaned and delivered back. Garments are counted
at pickup, at the store and at delivery; if any count doesn't match, the admin gets an alert.

**Tech stack:** Python 3.12–3.14 · Django 5.2 LTS · PostgreSQL · Bootstrap 5 · HTMX ·
Razorpay (test mode) · Chart.js

---

## Run on a new computer (Windows)

Do steps 1–3 **once per computer**.

### 1. Install Python
1. Download **Python 3.14** (3.12 or 3.13 also work) from <https://www.python.org/downloads/>.
2. Run the installer and **tick "Add python.exe to PATH"** at the bottom of the first screen.
3. Click **Install Now**.

### 2. Install PostgreSQL
1. Download the Windows installer (version 17 or 18) from <https://www.postgresql.org/download/windows/>.
2. Run it and keep the default options (port **5432**).
3. It asks for a password for the **postgres** admin user. **Write this password down.**
4. At the end it offers "Stack Builder". You don't need it, so untick it and click Finish.

### 3. Create the database and its user
1. Open the Start menu and launch **SQL Shell (psql)**.
2. Press **Enter** for Server, Database, Port and Username to accept the defaults.
3. Type the **postgres** password from step 2. Nothing shows while you type; that's normal.
4. Type these two lines and press Enter after each. Choose your own password in place of
   `MyStrongPass123`, keeping the single quotes:
   ```sql
   CREATE USER washo_user WITH PASSWORD 'MyStrongPass123' CREATEDB;
   CREATE DATABASE washo OWNER washo_user;
   ```
   You should see `CREATE ROLE` and then `CREATE DATABASE`.
   - `OWNER washo_user` lets our app create its tables.
   - `CREATEDB` lets Django create a temporary test database when tests run.
5. Type `\q` and press Enter to close the shell.

### 4. Get the project folder
Either:
- **Copy** the `WashO` folder (pen drive / zip), **but do not copy** the `venv` folder or the
  `.env` file. They belong to the old computer. If you copy them by mistake, setup.bat detects
  a broken `venv` and rebuilds it.
- **or** `git clone <repository-url>` if the project is on GitHub.

### 5. Run setup.bat
1. Open the `WashO` folder and **double-click `setup.bat`**. You need an internet connection
   the first time.
2. The first run stops with **"ACTION NEEDED"**. That is expected. It has created a file
   called `.env`.
3. Open `.env` in Notepad and replace `PUT_YOUR_DB_PASSWORD_HERE` with the password you chose
   in step 3. Save the file.
4. **Double-click `setup.bat` again.** It checks the database connection and creates all the
   tables. It finishes with **"Setup complete"**.

### 6. Create your admin login
Open PowerShell in the `WashO` folder: in File Explorer, click the address bar, type
`powershell` and press Enter. Then run:

```
venv\Scripts\python manage.py createsuperuser
```
Enter a 10-digit mobile number (for example `9999999999`) and a password. This is your admin
login.

### 7. Start WashO (every day)
**Double-click `start.bat`** in the WashO folder. It:
1. checks that PostgreSQL is running, and tells you how to start it if not,
2. installs any new Python packages (only needs internet when something was added),
3. applies any new database changes,
4. starts the website and **opens it in your browser** automatically.

The black window says **"WashO is running. Close this window to stop it."** Keep it open while
you use the website, and close it when you're done.

**Optional: Desktop shortcut.** Double-click `create_shortcut.bat` once. A **WashO** icon appears
on your Desktop. From then on, just double-click that icon to start WashO.

<details><summary>Starting it by hand instead (advanced)</summary>

```
venv\Scripts\python manage.py runserver
```
Then open <http://127.0.0.1:8000> yourself. Stop with **Ctrl + C**.
</details>

The admin site is at <http://127.0.0.1:8000/admin/>.

> `migrate` (run by setup.bat) also loads the master data automatically: the 4 roles, FAQs,
> the full price list (6 services, 35 items), the 3 Pune stores with their service areas,
> 6 daily pickup time slots, 4 sample coupons and the PL/pgSQL status-history trigger.
>
> Each computer has its own database, so users and orders are **not** copied between laptops.
> From Phase 8, `seed_demo` will fill a new database with the same demo data on any computer.

---

## Everyday commands
Run these from the `WashO` folder:

| What | Command |
|---|---|
| Start the website | Double-click `start.bat` (or the **WashO** Desktop shortcut) |
| Create the Desktop shortcut (once) | Double-click `create_shortcut.bat` |
| Run all automatic tests | `venv\Scripts\python manage.py test` |
| Reload the demo data | `venv\Scripts\python manage.py seed_demo --reset` |
| Check the database connection | `venv\Scripts\python scripts\check_db.py` |
| Apply new database changes (after pulling new code) | `venv\Scripts\python manage.py migrate` |
| Re-install packages (after requirements.txt changes) | `venv\Scripts\python -m pip install -r requirements.txt` |

Tip: running `setup.bat` again does all of the "after new code" steps for you.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Python was not found` | Install Python (step 1) with "Add python.exe to PATH" ticked, then open a **new** window. |
| `This Python version is not supported` | Install Python 3.14 (or 3.12/3.13). Other versions can stay installed. |
| `password authentication failed for user "washo_user"` | The password in `.env` doesn't match the one from step 3. Fix `DB_PASSWORD` in `.env`. |
| `database "washo" does not exist` | Repeat step 3. |
| `connection refused` / `could not connect to server` | PostgreSQL isn't running. Open **Services** (Win + R → `services.msc`), find **postgresql-x64-18** and click **Start**. |
| `Can create tables in schema public: NO` | In SQL Shell (as postgres): `ALTER DATABASE washo OWNER TO washo_user;` |
| `Can create databases (for tests): NO` | In SQL Shell (as postgres): `ALTER ROLE washo_user CREATEDB;` |
| start.bat says **"WashO already seems to be running"** | Another WashO window is already open. Use that one, or close it and start again. |
| start.bat says **"Can't connect to the PostgreSQL database"** | Start the PostgreSQL service (see `connection refused` above). |
| `psql` is not recognised | Use **SQL Shell (psql)** from the Start menu, or add `C:\Program Files\PostgreSQL\18\bin` to PATH. |
| Page looks unstyled (no colours) | Bootstrap loads from the internet; check your connection. |

---

## Project structure
```
WashO/
├── washo/          Project settings and main URL list
├── core/           Public pages (home, services, about, FAQ, contact)
├── accounts/       Custom user (login by mobile number), roles, sign-up, profile
├── catalog/        Service categories, items, per-item prices, express surcharge, price list
├── stores/         Cities, stores, service areas (pincodes), store locator
├── orders/         Booking, pickup slots + capacity, coupons, orders, status history (PL/pgSQL trigger)
├── tagging/        Staff panel: garment tagging + QR codes, damage photos, counts, mismatch alerts
├── delivery/       Agent panel (My jobs): pickups & deliveries with garment counts; agent assignment
├── payments/       Cash on Delivery collection, PDF invoices
├── dashboard/      Admin dashboard (Chart.js) reading the PostgreSQL revenue VIEW
├── docs/           Project report, synopsis, diagrams, data dictionary, test cases, viva prep
├── media/          Uploaded photos (created automatically, not in Git)
├── templates/      HTML templates (base layout + one folder per app)
├── static/         CSS and images
├── scripts/        Helper scripts used by setup.bat
├── setup.bat       One-click setup for Windows (run once per computer)
├── start.bat       Double-click to start WashO every day
├── create_shortcut.bat  Puts a WashO shortcut on the Desktop
├── requirements.txt  Exact package versions
└── .env.example    Template for the .env settings file
```

## Demo logins
`setup.bat` loads Pune demo data (`python manage.py seed_demo`): staff and 2 delivery agents per store,
20 customers and 60 orders over the last 6 weeks in every status, including 2 open garment-count mismatch
alerts. **Every demo account uses the password `Demo@1234`.**

| Role | Mobile number | Lands on |
|---|---|---|
| Admin | `9044000001` | Dashboard |
| Store Staff, Baner / Kothrud / Viman Nagar | `9022000001` / `9022000002` / `9022000003` | Staff panel |
| Delivery Agents, Baner | `9033000001`, `9033000002` | My jobs |
| Delivery Agents, Kothrud | `9033000003`, `9033000004` | My jobs |
| Delivery Agents, Viman Nagar | `9033000005`, `9033000006` | My jobs |
| Customers | `9011000001` … `9011000020` | My account |

To rebuild the demo data from scratch: `venv\Scripts\python manage.py seed_demo --reset`.
(Only demo accounts and their orders are removed; your own accounts and orders are kept.)

## Emails
While developing, every email (booking, each status change, delivery with the PDF invoice attached)
is **printed in the WashO window** instead of being sent. Customers without an email address get none.
To send real emails, see the `EMAIL_...` lines in `.env.example`.

## User roles
| Role | How the account is created |
|---|---|
| Customer | Signs up on the website |
| Store Staff | Admin creates the user, picks the **Store Staff** group and sets **Works at** (store) |
| Delivery Agent | Admin creates the user, picks the **Delivery Agent** group and sets **Works at** (store) |
| Admin | `manage.py createsuperuser` |
