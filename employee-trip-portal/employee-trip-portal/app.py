"""Employee Trip Management Portal - simple base project (Flask + SQLite)."""
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
DATABASE = os.path.join(os.path.dirname(__file__), "portal.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    department TEXT DEFAULT '',
    role TEXT NOT NULL DEFAULT 'employee'   -- employee | manager
);
CREATE TABLE IF NOT EXISTS trips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    destination TEXT NOT NULL,
    purpose TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    estimated_cost REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Pending', -- Pending | Approved | Rejected | Cancelled
    manager_comment TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


# ---------- database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript(SCHEMA)
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        seed = [
            ("Alice Manager", "manager@example.com", "manager123", "Operations", "manager"),
            ("Bob Employee", "employee@example.com", "employee123", "Sales", "employee"),
        ]
        for name, email, pw, dept, role in seed:
            db.execute(
                "INSERT INTO users (name,email,password_hash,department,role) VALUES (?,?,?,?,?)",
                (name, email, generate_password_hash(pw), dept, role),
            )
    db.commit()
    db.close()


# ---------- auth ----------
def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*a, **kw)
    return wrapped


def manager_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if session.get("role") != "manager":
            flash("Managers only.", "error")
            return redirect(url_for("dashboard"))
        return view(*a, **kw)
    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute(
            "SELECT * FROM users WHERE email=?", (request.form["email"].strip().lower(),)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session.update(user_id=user["id"], name=user["name"], role=user["role"])
            return redirect(url_for("dashboard"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        try:
            get_db().execute(
                "INSERT INTO users (name,email,password_hash,department) VALUES (?,?,?,?)",
                (f["name"].strip(), f["email"].strip().lower(),
                 generate_password_hash(f["password"]), f.get("department", "").strip()),
            )
            get_db().commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- trips ----------
def validate_trip(f):
    errors = []
    if not f.get("destination", "").strip():
        errors.append("Destination is required.")
    if not f.get("purpose", "").strip():
        errors.append("Purpose is required.")
    try:
        start = date.fromisoformat(f.get("start_date", ""))
        end = date.fromisoformat(f.get("end_date", ""))
        if end < start:
            errors.append("End date cannot be before start date.")
    except ValueError:
        errors.append("Valid start and end dates are required.")
    try:
        if float(f.get("estimated_cost", "")) < 0:
            errors.append("Cost cannot be negative.")
    except ValueError:
        errors.append("Estimated cost must be a number.")
    return errors


@app.route("/")
@login_required
def dashboard():
    db = get_db()
    stats = {s: db.execute(
        "SELECT COUNT(*) FROM trips WHERE user_id=? AND status=?",
        (session["user_id"], s)).fetchone()[0]
        for s in ("Pending", "Approved", "Rejected", "Cancelled")}
    trips = db.execute(
        "SELECT * FROM trips WHERE user_id=? ORDER BY start_date DESC", (session["user_id"],)
    ).fetchall()
    return render_template("dashboard.html", trips=trips, stats=stats)


@app.route("/trips/new", methods=["GET", "POST"])
@login_required
def new_trip():
    if request.method == "POST":
        errors = validate_trip(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            f = request.form
            get_db().execute(
                "INSERT INTO trips (user_id,destination,purpose,start_date,end_date,estimated_cost)"
                " VALUES (?,?,?,?,?,?)",
                (session["user_id"], f["destination"].strip(), f["purpose"].strip(),
                 f["start_date"], f["end_date"], float(f["estimated_cost"])),
            )
            get_db().commit()
            flash("Trip request submitted.", "success")
            return redirect(url_for("dashboard"))
    return render_template("trip_form.html", trip=request.form, editing=False)


def own_pending_trip(trip_id):
    return get_db().execute(
        "SELECT * FROM trips WHERE id=? AND user_id=? AND status='Pending'",
        (trip_id, session["user_id"])).fetchone()


@app.route("/trips/<int:trip_id>/edit", methods=["GET", "POST"])
@login_required
def edit_trip(trip_id):
    trip = own_pending_trip(trip_id)
    if not trip:
        flash("Only your pending trips can be edited.", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        errors = validate_trip(request.form)
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            f = request.form
            get_db().execute(
                "UPDATE trips SET destination=?,purpose=?,start_date=?,end_date=?,estimated_cost=? WHERE id=?",
                (f["destination"].strip(), f["purpose"].strip(), f["start_date"],
                 f["end_date"], float(f["estimated_cost"]), trip_id),
            )
            get_db().commit()
            flash("Trip updated.", "success")
            return redirect(url_for("dashboard"))
        trip = request.form
    return render_template("trip_form.html", trip=trip, editing=True, trip_id=trip_id)


@app.route("/trips/<int:trip_id>/cancel", methods=["POST"])
@login_required
def cancel_trip(trip_id):
    if own_pending_trip(trip_id):
        get_db().execute("UPDATE trips SET status='Cancelled' WHERE id=?", (trip_id,))
        get_db().commit()
        flash("Trip cancelled.", "success")
    return redirect(url_for("dashboard"))


# ---------- manager ----------
@app.route("/manage")
@manager_required
def manage():
    status = request.args.get("status", "Pending")
    q = ("SELECT t.*, u.name AS employee, u.department FROM trips t "
         "JOIN users u ON u.id=t.user_id ")
    args = ()
    if status != "All":
        q += "WHERE t.status=? "
        args = (status,)
    trips = get_db().execute(q + "ORDER BY t.created_at DESC", args).fetchall()
    return render_template("manage.html", trips=trips, status=status)


@app.route("/manage/<int:trip_id>/decide", methods=["POST"])
@manager_required
def decide(trip_id):
    decision = request.form.get("decision")
    if decision in ("Approved", "Rejected"):
        get_db().execute(
            "UPDATE trips SET status=?, manager_comment=? WHERE id=? AND status='Pending'",
            (decision, request.form.get("comment", "").strip(), trip_id),
        )
        get_db().commit()
        flash(f"Trip {decision.lower()}.", "success")
    return redirect(url_for("manage"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
