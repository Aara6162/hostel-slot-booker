import os
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-only-change-me")
DATABASE = os.path.join(app.root_path, "booker.db")

OPEN_HOUR = 6
CLOSE_HOUR = 22
MAX_PER_DAY = 2
MAX_DAYS_AHEAD = 7


def now_ist():
    return datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql") as f:
            db.executescript(f.read().decode("utf-8"))
        count = db.execute("SELECT COUNT(*) FROM resources").fetchone()[0]
        if count == 0:
            for name in ["Study Room", "Laundry Machine 1", "Gym"]:
                db.execute("INSERT INTO resources (name) VALUES (?)", (name,))
            db.commit()


init_db()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access only.", "error")
            return redirect(url_for("index"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3 or len(username) > 30:
            flash("Username must be 3 to 30 characters.", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
            return render_template("register.html")

        db = get_db()
        user_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        role = "admin" if user_count == 0 else "user"

        try:
            db.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), role),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("That username is already taken.", "error")
            return render_template("register.html")

        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        flash("Logged in successfully.", "success")
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    db = get_db()
    now = now_ist()
    today = now.date()
    max_date = today + timedelta(days=MAX_DAYS_AHEAD)

    resources = db.execute("SELECT * FROM resources ORDER BY name").fetchall()
    if not resources:
        flash("No resources available yet. Ask the admin to add one.", "error")
        return render_template(
            "index.html", resources=[], slots=[], selected_resource_id=None,
            selected_resource_name="", selected_date=str(today),
            today=str(today), max_date=str(max_date),
        )

    try:
        selected_resource_id = int(request.args.get("resource_id", resources[0]["id"]))
    except ValueError:
        selected_resource_id = resources[0]["id"]
    selected = next((r for r in resources if r["id"] == selected_resource_id), resources[0])
    selected_resource_id = selected["id"]

    try:
        selected_date = datetime.strptime(
            request.args.get("date", str(today)), "%Y-%m-%d"
        ).date()
    except ValueError:
        selected_date = today
    if selected_date < today or selected_date > max_date:
        flash("Pick a date between today and the next 7 days.", "error")
        selected_date = today

    booked = db.execute(
        "SELECT slot_hour, user_id FROM bookings WHERE resource_id = ? AND booking_date = ?",
        (selected_resource_id, str(selected_date)),
    ).fetchall()
    booked_map = {b["slot_hour"]: b["user_id"] for b in booked}

    slots = []
    for hour in range(OPEN_HOUR, CLOSE_HOUR):
        if selected_date == today and hour <= now.hour:
            status = "past"
        elif hour in booked_map:
            status = "mine" if booked_map[hour] == session["user_id"] else "taken"
        else:
            status = "free"
        slots.append({
            "hour": hour,
            "label": f"{hour:02d}:00 - {hour + 1:02d}:00",
            "status": status,
        })

    return render_template(
        "index.html", resources=resources, slots=slots,
        selected_resource_id=selected_resource_id,
        selected_resource_name=selected["name"],
        selected_date=str(selected_date),
        today=str(today), max_date=str(max_date),
    )


@app.route("/book", methods=["POST"])
@login_required
def book():
    db = get_db()
    now = now_ist()
    today = now.date()

    try:
        resource_id = int(request.form.get("resource_id", ""))
        hour = int(request.form.get("hour", ""))
        booking_date = datetime.strptime(request.form.get("date", ""), "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid booking request.", "error")
        return redirect(url_for("index"))

    back = redirect(url_for("index", resource_id=resource_id, date=str(booking_date)))

    resource = db.execute("SELECT * FROM resources WHERE id = ?", (resource_id,)).fetchone()
    if resource is None:
        flash("That resource does not exist.", "error")
        return redirect(url_for("index"))

    if hour < OPEN_HOUR or hour >= CLOSE_HOUR:
        flash("That time is outside opening hours.", "error")
        return back

    if booking_date < today or booking_date > today + timedelta(days=MAX_DAYS_AHEAD):
        flash("You can only book from today up to 7 days ahead.", "error")
        return back
    if booking_date == today and hour <= now.hour:
        flash("You cannot book a slot that has already started.", "error")
        return back

    count = db.execute(
        "SELECT COUNT(*) FROM bookings WHERE user_id = ? AND booking_date = ?",
        (session["user_id"], str(booking_date)),
    ).fetchone()[0]
    if count >= MAX_PER_DAY:
        flash("Limit reached: maximum 2 bookings per day.", "error")
        return back

    try:
        db.execute(
            "INSERT INTO bookings (user_id, resource_id, booking_date, slot_hour) VALUES (?, ?, ?, ?)",
            (session["user_id"], resource_id, str(booking_date), hour),
        )
        db.commit()
    except sqlite3.IntegrityError:
        flash("Sorry, someone just booked that slot.", "error")
        return back

    flash(f"Booked {resource['name']} on {booking_date} at {hour:02d}:00.", "success")
    return back


@app.route("/my-bookings")
@login_required
def my_bookings():
    db = get_db()
    today = str(now_ist().date())
    bookings = db.execute(
        """SELECT b.id, b.booking_date, b.slot_hour, r.name AS resource_name
           FROM bookings b JOIN resources r ON r.id = b.resource_id
           WHERE b.user_id = ? AND b.booking_date >= ?
           ORDER BY b.booking_date, b.slot_hour""",
        (session["user_id"], today),
    ).fetchall()
    return render_template("my_bookings.html", bookings=bookings)


@app.route("/cancel/<int:booking_id>", methods=["POST"])
@login_required
def cancel_booking(booking_id):
    db = get_db()
    booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()

    if booking is None:
        flash("Booking not found.", "error")
        return redirect(url_for("my_bookings"))

    if booking["user_id"] != session["user_id"] and session.get("role") != "admin":
        flash("You cannot cancel someone else's booking.", "error")
        return redirect(url_for("my_bookings"))

    db.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
    db.commit()
    flash("Booking cancelled. The slot is free again.", "success")
    return redirect(url_for("my_bookings"))


@app.route("/admin")
@login_required
@admin_required
def admin():
    return "Admin page (coming soon)"


if __name__ == "__main__":
    app.run(debug=True)
    