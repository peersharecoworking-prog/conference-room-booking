import os, sqlite3, secrets
from datetime import datetime, date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash

BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DB_PATH", os.path.join(BASE, "bookings.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-before-deploying")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_code TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            company TEXT DEFAULT '',
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            attendees INTEGER NOT NULL,
            purpose TEXT DEFAULT '',
            booking_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Confirmed',
            created_at TEXT NOT NULL
        )""")
        con.execute("""CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")
        defaults = {
            "room_name": "Conference Room",
            "capacity": "10",
            "open_time": "09:00",
            "close_time": "18:00",
            "slot_minutes": "60",
            "admin_hash": generate_password_hash(os.environ.get("ADMIN_PASSWORD", "ChangeMe123!"))
        }
        for k, v in defaults.items():
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k,v))

def setting(key):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else ""

def set_setting(key, value):
    with db() as con:
        con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,str(value)))

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return fn(*args, **kwargs)
    return wrapped

def overlaps(day, start, end, exclude_id=None, con=None):
    sql = """SELECT COUNT(*) n FROM bookings
             WHERE booking_date=? AND status IN ('Confirmed','Blocked')
             AND start_time < ? AND end_time > ?"""
    args = [day, end, start]
    if exclude_id:
        sql += " AND id != ?"; args.append(exclude_id)
    if con is not None:
        return con.execute(sql, args).fetchone()["n"] > 0
    with db() as connection:
        return connection.execute(sql, args).fetchone()["n"] > 0

def valid_window(day, start, end):
    try:
        d = date.fromisoformat(day)
        s = datetime.strptime(start, "%H:%M").time()
        e = datetime.strptime(end, "%H:%M").time()
        op = datetime.strptime(setting("open_time"), "%H:%M").time()
        cl = datetime.strptime(setting("close_time"), "%H:%M").time()
        return d >= date.today() and s >= op and e <= cl and e > s
    except Exception:
        return False

@app.context_processor
def inject_globals():
    return {"room_name": setting("room_name") or "Conference Room"}

@app.route("/")
def index():
    return render_template("index.html", today=date.today().isoformat(),
                           capacity=int(setting("capacity") or 10),
                           open_time=setting("open_time"), close_time=setting("close_time"),
                           slot_minutes=int(setting("slot_minutes") or 60))

@app.route("/availability")
def availability():
    day = request.args.get("date","")
    try: date.fromisoformat(day)
    except: return jsonify({"error":"Choose a valid date."}), 400
    with db() as con:
        rows = con.execute("""SELECT start_time,end_time FROM bookings
            WHERE booking_date=? AND status IN ('Confirmed','Blocked')""",(day,)).fetchall()
    return jsonify({"busy":[{"start":r["start_time"],"end":r["end_time"]} for r in rows],
                    "open":setting("open_time"),"close":setting("close_time"),
                    "slot_minutes":int(setting("slot_minutes") or 60)})

@app.route("/book", methods=["POST"])
def book():
    f = request.form
    name, email, phone = f.get("name","").strip(), f.get("email","").strip(), f.get("phone","").strip()
    company, purpose = f.get("company","").strip(), f.get("purpose","").strip()
    day, start = f.get("date",""), f.get("start_time","")
    try:
        attendees = int(f.get("attendees","1"))
        duration = int(f.get("duration","60"))
        s = datetime.strptime(start,"%H:%M")
        end = (s + timedelta(minutes=duration)).strftime("%H:%M")
    except:
        flash("Please check the date, time, attendee count and duration.", "error")
        return redirect(url_for("index"))
    if not name or not email or not phone or attendees < 1 or attendees > int(setting("capacity") or 10):
        flash("Please complete all required details. Attendees must be within room capacity.", "error")
        return redirect(url_for("index"))
    if not valid_window(day,start,end):
        flash("That time is outside the room's booking hours. Please choose another slot.", "error")
        return redirect(url_for("index"))
    code = "CR-" + secrets.token_hex(3).upper()
    with db() as con:
        con.execute("BEGIN IMMEDIATE")
        if overlaps(day,start,end,con=con):
            flash("Sorry, this time has just been booked. Please choose another available slot.", "error")
            return redirect(url_for("index"))
        try:
            con.execute("""INSERT INTO bookings
                (booking_code,client_name,company,email,phone,attendees,purpose,booking_date,start_time,end_time,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (code,name,company,email,phone,attendees,purpose,day,start,end,"Confirmed",datetime.now().isoformat(timespec="minutes")))
        except sqlite3.IntegrityError:
            flash("We couldn't confirm that slot. Please try another time.", "error")
            return redirect(url_for("index"))
    return render_template("confirmation.html", code=code, name=name, day=day, start=start, end=end)

@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    if request.method == "POST":
        with db() as con:
            row = con.execute("SELECT value FROM settings WHERE key='admin_hash'").fetchone()
        if row and check_password_hash(row["value"], request.form.get("password","")):
            session["admin"] = True
            return redirect(url_for("admin"))
        flash("Incorrect password.", "error")
    return render_template("login.html")

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/admin")
@admin_required
def admin():
    selected = request.args.get("date", date.today().isoformat())
    try: date.fromisoformat(selected)
    except: selected = date.today().isoformat()
    with db() as con:
        rows = con.execute("""SELECT * FROM bookings WHERE booking_date=?
            ORDER BY start_time""",(selected,)).fetchall()
        upcoming = con.execute("""SELECT * FROM bookings WHERE booking_date>=?
            ORDER BY booking_date,start_time LIMIT 30""",(date.today().isoformat(),)).fetchall()
    return render_template("admin.html", rows=rows, upcoming=upcoming, selected=selected,
        capacity=setting("capacity"), open_time=setting("open_time"), close_time=setting("close_time"),
        slot_minutes=setting("slot_minutes"))

@app.route("/admin/cancel/<int:booking_id>", methods=["POST"])
@admin_required
def cancel_booking(booking_id):
    with db() as con:
        con.execute("UPDATE bookings SET status='Cancelled' WHERE id=? AND status='Confirmed'",(booking_id,))
    flash("Booking cancelled.", "success")
    return redirect(url_for("admin", date=request.form.get("date",date.today().isoformat())))

@app.route("/admin/block", methods=["POST"])
@admin_required
def block_time():
    day,start,end = request.form.get("date",""),request.form.get("start_time",""),request.form.get("end_time","")
    if not valid_window(day,start,end):
        flash("Please enter a valid block time within opening hours.", "error")
    else:
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            if overlaps(day,start,end,con=con):
                flash("That period overlaps an existing booking or block.", "error")
                return redirect(url_for("admin",date=day))
            con.execute("""INSERT INTO bookings
                (booking_code,client_name,email,phone,attendees,booking_date,start_time,end_time,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                ("BL-"+secrets.token_hex(3).upper(),"Admin block","admin@local","—",0,day,start,end,"Blocked",datetime.now().isoformat(timespec="minutes")))
        flash("Time blocked successfully.", "success")
    return redirect(url_for("admin",date=day))

@app.route("/admin/settings", methods=["POST"])
@admin_required
def save_settings():
    room = request.form.get("room_name","").strip() or "Conference Room"
    cap = request.form.get("capacity","10")
    op,cl = request.form.get("open_time","09:00"),request.form.get("close_time","18:00")
    slot = request.form.get("slot_minutes","60")
    try:
        if int(cap)<1 or int(slot) not in (30,60) or datetime.strptime(op,"%H:%M") >= datetime.strptime(cl,"%H:%M"):
            raise ValueError()
    except:
        flash("Please check capacity, opening hours and slot length.", "error")
        return redirect(url_for("admin"))
    for k,v in {"room_name":room,"capacity":cap,"open_time":op,"close_time":cl,"slot_minutes":slot}.items():
        set_setting(k,v)
    newpass = request.form.get("new_password","")
    if newpass:
        if len(newpass)<10:
            flash("New admin password must be at least 10 characters.", "error")
            return redirect(url_for("admin"))
        set_setting("admin_hash",generate_password_hash(newpass))
    flash("Settings saved.", "success")
    return redirect(url_for("admin"))

@app.route("/health")
def health():
    return {"status":"ok"}

init_db()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=False)
