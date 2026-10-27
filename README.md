# Hostel Slot Booker

A web application for booking shared hostel facilities (study room, laundry machine, gym) with fair, conflict-free scheduling.

**Live app:** https://hostel-slot-booker.onrender.com

## Problem Statement

Hostel residents share limited facilities such as the study room, laundry machines and gym. Without a system, people double-book, hog slots, and argue over who had a facility first.

## Target Users

- **Residents:** book and manage their own slots.
- **Warden / admin:** adds facilities and monitors or cancels any booking.

## Solution

Residents log in, pick a facility and a date, and see live availability for every hourly slot. Bookings are validated by the server, so conflicts and abuse are blocked. Admins manage facilities and oversee all bookings.

## Key Features

1. **Authentication:** register and log in with hashed passwords and sessions. The first registered user becomes admin.
2. **Live availability:** hourly slots per facility per date, marked free, booked, yours, or past.
3. **Validated booking:** blocks past slots, dates beyond 7 days, invalid input, and more than 2 bookings per user per day. A database UNIQUE constraint makes double-booking impossible even under simultaneous requests.
4. **Cancel bookings:** users cancel their own bookings; ownership is enforced server-side.
5. **Admin panel:** role-based access to add facilities, view all upcoming bookings, and cancel any booking.
6. **Error handling:** clear success and error messages, plus custom 404 and 500 pages.

## Tech Stack

- Python 3, Flask
- SQLite
- Jinja2 HTML templates
- Gunicorn (production server)
- Render (hosting), GitHub (version control)

## Architecture

```text
Browser
   |
Flask app (app.py)
   |-- Auth: register / login / logout, session, login_required, admin_required
   |-- Booking logic: availability, validation, create, cancel
   |-- Admin routes: add resource, list and cancel all bookings
   |
SQLite (schema.sql): users, resources, bookings
```

- `app.py`: routes, validation rules, and database access
- `schema.sql`: table definitions, including `UNIQUE (resource_id, booking_date, slot_hour)`
- `templates/`: Jinja2 pages sharing a base layout

## Local Setup

```bash
git clone https://github.com/Aara6162/hostel-slot-booker.git
cd hostel-slot-booker
python -m venv venv
venv\Scripts\activate        # Windows (on Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The database is created automatically on first run. Register the first account to get admin access.

## Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `SECRET_KEY` | Signs session cookies. Set a long random value in production. | `dev-only-change-me` (local development only) |

## Deployment

Deployed on Render (free tier): https://hostel-slot-booker.onrender.com

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- `SECRET_KEY` is set as an environment variable on Render, not in the code.

**Known limitation:** the free tier sleeps when idle (first load can take about a minute), and the SQLite file resets on each redeploy. A production version would use a managed database such as PostgreSQL.

## Security

- Passwords stored as salted hashes, never in plain text
- Parameterized SQL queries throughout
- Server-side validation of all booking input
- Authorization checks on cancel and admin routes
- No secrets committed to the repository