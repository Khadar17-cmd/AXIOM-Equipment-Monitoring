from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, session, flash
from flask_cors import CORS
from database import get_connection, initialize_database
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import random
import csv
import os
import smtplib
import re
from email.message import EmailMessage
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "iot-ai-demo-secret-change-this-in-production")
CORS(app)
initialize_database()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login", next=request.path))
        if session.get("role") != "admin":
            return render_template("access_denied.html"), 403
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {"current_user": session.get("full_name"), "current_role": session.get("role")}


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        conn = get_connection()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and user["active"] and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["full_name"] = user["full_name"]
            session["role"] = user["role"]
            return redirect(request.args.get("next") or url_for("dashboard"))
        return render_template("login.html", error="Invalid username or password, or account is inactive.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html")

@app.route("/equipment")
@login_required
def equipment_page():
    return render_template("equipment.html")

@app.route("/equipment/add", methods=["GET", "POST"])
@admin_required
def add_equipment_page():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "Training equipment").strip()
        location = request.form.get("location", "").strip()
        description = request.form.get("description", "").strip()
        status = request.form.get("status", "Active")
        if not name or status not in ("Active", "Warning", "Offline"):
            flash("Enter an equipment name and valid status.", "error")
            return redirect(url_for("add_equipment_page"))
        conn = get_connection()
        cur = conn.execute("INSERT INTO equipment (name,category,location,description,status,temperature,vibration,power,usage_hours,last_maintenance) VALUES (?,?,?,?,?,0,0,0,0,?)",
                           (name, category, location, description, status, datetime.now().strftime("%Y-%m-%d")))
        equipment_id = cur.lastrowid
        row = conn.execute("SELECT * FROM equipment WHERE id=?", (equipment_id,)).fetchone()
        save_history(conn, dict(row))
        conn.commit(); conn.close()
        flash("Equipment registered successfully.", "success")
        return redirect(url_for("equipment_page"))
    return render_template("add_equipment.html")

@app.route("/assistant")
@login_required
def chatbot_page():
    return render_template("chatbot.html")

@app.route("/notifications")
@admin_required
def notifications_page():
    conn = get_connection()
    recipients = conn.execute("SELECT * FROM notification_recipients ORDER BY id DESC").fetchall()
    conn.close()
    smtp_ready = all(os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"))
    return render_template("notifications.html", recipients=recipients, smtp_ready=smtp_ready)

@app.route("/notifications/add", methods=["POST"])
@admin_required
def add_notification_recipient():
    email = request.form.get("email", "").strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        flash("Enter a valid email address.", "error")
        return redirect(url_for("notifications_page"))
    conn = get_connection()
    try:
        conn.execute("INSERT INTO notification_recipients (email) VALUES (?)", (email,))
        conn.commit(); flash("Notification recipient added.", "success")
    except Exception:
        flash("That email address is already registered.", "error")
    conn.close()
    return redirect(url_for("notifications_page"))

@app.route("/notifications/delete/<int:recipient_id>", methods=["POST"])
@admin_required
def delete_notification_recipient(recipient_id):
    conn = get_connection(); conn.execute("DELETE FROM notification_recipients WHERE id=?", (recipient_id,)); conn.commit(); conn.close()
    return redirect(url_for("notifications_page"))

@app.route("/api/assistant", methods=["POST"])
@login_required
def assistant_reply():
    data = request.get_json(silent=True) or {}
    question = str(data.get("message", "")).strip().lower()
    if not question:
        return jsonify({"answer": "Please enter a question about your equipment."}), 400
    conn = get_connection()
    rows = [dict(r) for r in conn.execute("SELECT * FROM equipment ORDER BY id").fetchall()]
    conn.close()
    critical = [x for x in rows if x["status"] == "Critical"]
    warning = [x for x in rows if x["status"] == "Warning"]
    offline = [x for x in rows if x["status"] == "Offline"]
    if any(k in question for k in ("critical", "danger", "urgent")):
        answer = ("Critical equipment: " + ", ".join(f'{x["name"]} (temperature {x["temperature"]} °C, vibration {x["vibration"]})' for x in critical) + ". Arrange an inspection and follow your workshop safety procedure.") if critical else "There are currently no machines marked Critical. Continue monitoring the readings."
    elif "warning" in question or "alert" in question:
        answer = ("Machines requiring attention: " + ", ".join(x["name"] for x in warning + critical) + ". Check the readings and inspect the machine before continued operation.") if warning or critical else "There are no active Warning or Critical conditions at the moment."
    elif "temperature" in question or "heat" in question:
        answer = "Current temperature readings: " + "; ".join(f'{x["name"]}: {x["temperature"]} °C ({x["status"]})' for x in rows) + ". The prototype uses simulated sensor values."
    elif "vibration" in question or "shake" in question:
        answer = "Current vibration readings: " + "; ".join(f'{x["name"]}: {x["vibration"]} ({x["status"]})' for x in rows) + ". High vibration can be associated with imbalance, loose mounting or bearing wear; inspect safely."
    elif "power" in question or "energy" in question:
        answer = "Current power readings: " + "; ".join(f'{x["name"]}: {x["power"]} kW' for x in rows) + ". These values are simulated."
    elif "offline" in question:
        answer = ("Offline equipment: " + ", ".join(x["name"] for x in offline) + ". Check the power supply and connectivity in a real installation.") if offline else "No equipment is currently marked Offline."
    elif "maintenance" in question or "service" in question or "fix" in question:
        answer = "Maintenance guidance: stop and isolate equipment when required by your workshop procedure, inspect for visible damage or loose parts, review temperature and vibration trends, record the work, and only return the machine to service after an authorized check. Current attention list: " + (", ".join(x["name"] for x in warning + critical) or "none") + "."
    elif "health" in question or "score" in question:
        answer = "Equipment health scores: " + "; ".join(f'{x["name"]}: {calculate_health(x["temperature"],x["vibration"],x["power"],x["status"])["health_score"]}%' for x in rows) + ". Scores are rule-based estimates, not trained AI predictions."
    elif "how many" in question or "total" in question or "equipment" in question or "machine" in question:
        answer = f"There are {len(rows)} registered machines: {len([x for x in rows if x['status']=='Active'])} Active, {len(warning)} Warning, {len(critical)} Critical and {len(offline)} Offline."
    else:
        answer = "I can answer questions about equipment status, critical alerts, temperature, vibration, power, health scores and basic maintenance guidance. Try asking: 'Which equipment is critical?'"
    return jsonify({"answer": answer})

@app.route("/ai-detection")
@login_required
def ai_detection_page():
    return render_template("ai_detection.html")

@app.route("/alerts")
@login_required
def alerts_page():
    return render_template("alerts.html")

@app.route("/analytics")
@login_required
def analytics_page():
    return render_template("analytics.html")

@app.route("/users")
@admin_required
def users_page():
    return render_template("users.html")

def calculate_health(temperature, vibration, power, status):
    """Rule-based equipment health estimate (0-100), not a trained AI prediction."""
    if status == "Offline":
        return {"health_score": 0, "health_label": "Offline"}

    score = 100
    temperature = float(temperature or 0)
    vibration = float(vibration or 0)
    power = float(power or 0)

    if temperature > 80:
        score -= 40
    elif temperature >= 65:
        score -= 25
    elif temperature >= 50:
        score -= 10

    if vibration > 5.5:
        score -= 40
    elif vibration >= 4:
        score -= 25
    elif vibration > 2:
        score -= 10

    if power > 7:
        score -= 20
    elif power > 6:
        score -= 10

    if status == "Critical":
        score = min(score, 35)
    elif status == "Warning":
        score = min(score, 75)

    score = max(0, min(100, score))
    label = "Healthy" if score >= 80 else ("Warning" if score >= 50 else "Critical")
    return {"health_score": score, "health_label": label}


@app.route("/api/equipment")
@login_required
def get_equipment():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM equipment ORDER BY id").fetchall()
    conn.close()
    equipment = []
    for row in rows:
        item = dict(row)
        item.update(calculate_health(item["temperature"], item["vibration"], item["power"], item["status"]))
        equipment.append(item)
    return jsonify(equipment)

@app.route("/api/stats")
@login_required
def stats():
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    active = conn.execute("SELECT COUNT(*) FROM equipment WHERE status='Active'").fetchone()[0]
    warning = conn.execute("SELECT COUNT(*) FROM equipment WHERE status='Warning'").fetchone()[0]
    critical = conn.execute("SELECT COUNT(*) FROM equipment WHERE status='Critical'").fetchone()[0]
    offline = conn.execute("SELECT COUNT(*) FROM equipment WHERE status='Offline'").fetchone()[0]
    conn.close()
    return jsonify({"total": total, "active": active, "warning": warning, "critical": critical, "offline": offline})

def save_history(conn, row):
    conn.execute("""
        INSERT INTO sensor_history
        (equipment_id, temperature, vibration, power, usage_hours, status, recorded_at)
        VALUES (?,?,?,?,?,?,?)
    """, (row["id"], row["temperature"], row["vibration"], row["power"],
          row["usage_hours"], row["status"], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

def notify_equipment_status(equipment):
    if equipment.get("status") not in ("Warning", "Critical"):
        return
    conn = get_connection()
    last = conn.execute("SELECT sent_at FROM notification_log WHERE equipment_id=? AND status=? ORDER BY id DESC LIMIT 1", (equipment["id"], equipment["status"])).fetchone()
    if last:
        try:
            from datetime import datetime, timedelta
            previous = datetime.strptime(last["sent_at"], "%Y-%m-%d %H:%M:%S")
            if datetime.now() - previous < timedelta(minutes=30):
                conn.close(); return
        except ValueError:
            pass
    recipients = [r[0] for r in conn.execute("SELECT email FROM notification_recipients").fetchall()]
    message = f'{equipment["name"]} is currently {equipment["status"]}. Temperature: {equipment["temperature"]} °C; vibration: {equipment["vibration"]}; power: {equipment["power"]} kW.'
    conn.execute("INSERT INTO notification_log (equipment_id,status,message) VALUES (?,?,?)", (equipment["id"], equipment["status"], message))
    conn.commit(); conn.close()
    required = ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]
    if not recipients or not all(os.getenv(k) for k in required):
        return
    try:
        mail = EmailMessage(); mail["Subject"] = f'{equipment["status"]}: {equipment["name"]} equipment alert'; mail["From"] = os.getenv("SMTP_FROM"); mail["To"] = ", ".join(recipients); mail.set_content("AXIOM EQUIPMENT MONITORING ALERT\n\n" + message + "\n\nThis alert was generated by the project monitoring prototype.")
        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587")), timeout=10) as server:
            server.starttls(); server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")); server.send_message(mail)
    except Exception as exc:
        app.logger.warning("Email notification could not be sent: %s", exc)

@app.route("/api/simulate", methods=["POST"])
@admin_required
def simulate():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM equipment").fetchall()
    updated = []
    for row in rows:
        if row["status"] == "Offline":
            continue
        temperature = round(random.uniform(30, 90), 1)
        vibration = round(random.uniform(0.5, 6.5), 1)
        power = round(random.uniform(1.5, 7.5), 1)
        usage = round(row["usage_hours"] + random.uniform(0.01, 0.08), 2)
        if temperature >= 80 or vibration >= 5.5:
            status = "Critical"
        elif temperature >= 65 or vibration >= 4:
            status = "Warning"
        else:
            status = "Active"
        conn.execute("""
            UPDATE equipment SET status=?, temperature=?, vibration=?, power=?, usage_hours=? WHERE id=?
        """, (status, temperature, vibration, power, usage, row["id"]))
        updated_row = dict(row)
        updated_row.update({"temperature": temperature, "vibration": vibration, "power": power, "usage_hours": usage, "status": status})
        save_history(conn, updated_row)
        updated.append(row["id"])
    conn.commit()
    conn.close()
    for item_id in updated:
        notify_conn = get_connection()
        item = notify_conn.execute("SELECT * FROM equipment WHERE id=?", (item_id,)).fetchone()
        notify_conn.close()
        if item: notify_equipment_status(dict(item))
    return jsonify({"message": "IoT simulation updated", "updated": updated, "time": datetime.now().strftime("%H:%M:%S")})

@app.route("/api/simulate-fault/<int:equipment_id>", methods=["POST"])
@admin_required
def simulate_fault(equipment_id):
    conn = get_connection()
    conn.execute("UPDATE equipment SET status='Critical', temperature=88.0, vibration=6.2, power=7.1 WHERE id=?", (equipment_id,))
    row = conn.execute("SELECT * FROM equipment WHERE id=?", (equipment_id,)).fetchone()
    if row:
        save_history(conn, dict(row))
    conn.commit()
    conn.close()
    if row: notify_equipment_status(dict(row))
    return jsonify({"message": "Fault simulated successfully"})

@app.route("/api/analytics")
@login_required
def analytics():
    conn = get_connection()
    averages = conn.execute("""
        SELECT ROUND(AVG(temperature),2) avg_temperature, ROUND(AVG(vibration),2) avg_vibration,
               ROUND(AVG(power),2) avg_power, ROUND(SUM(usage_hours),2) total_usage
        FROM equipment WHERE status != 'Offline'
    """).fetchone()
    status_rows = conn.execute("SELECT status, COUNT(*) count FROM equipment GROUP BY status").fetchall()
    equipment_rows = conn.execute("""
        SELECT name, status, ROUND(temperature,1) temperature, ROUND(vibration,1) vibration,
               ROUND(power,1) power, ROUND(usage_hours,2) usage_hours, last_maintenance
        FROM equipment ORDER BY usage_hours DESC
    """).fetchall()
    trend = conn.execute("""
        SELECT strftime('%H:%M', recorded_at) time, ROUND(AVG(temperature),1) temperature,
               ROUND(AVG(vibration),1) vibration, ROUND(AVG(power),1) power
        FROM sensor_history GROUP BY strftime('%Y-%m-%d %H:%M', recorded_at)
        ORDER BY recorded_at DESC LIMIT 12
    """).fetchall()
    conn.close()
    return jsonify({"averages": dict(averages), "status_distribution": [dict(x) for x in status_rows],
                    "equipment": [dict(x) for x in equipment_rows], "trend": list(reversed([dict(x) for x in trend]))})

@app.route("/api/report.csv")
@login_required
def report_csv():
    conn = get_connection()
    rows = conn.execute("SELECT id,name,status,temperature,vibration,power,usage_hours,last_maintenance FROM equipment ORDER BY id").fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Equipment ID", "Equipment", "Status", "Health Score (%)", "Health Label", "Temperature (C)", "Vibration", "Power (kW)", "Usage (hours)", "Last Maintenance"])
    for r in rows:
        health = calculate_health(r["temperature"], r["vibration"], r["power"], r["status"])
        writer.writerow([r["id"],r["name"],r["status"],health["health_score"],health["health_label"],r["temperature"],r["vibration"],r["power"],r["usage_hours"],r["last_maintenance"]])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition":"attachment; filename=equipment_report.csv"})

@app.route("/api/history")
@login_required
def history():
    conn = get_connection()
    rows = conn.execute("""
        SELECT h.*, e.name FROM sensor_history h JOIN equipment e ON e.id=h.equipment_id
        ORDER BY h.recorded_at DESC LIMIT 100
    """).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/reset", methods=["POST"])
@admin_required
def reset():
    conn = get_connection()
    conn.execute("DELETE FROM sensor_history")
    conn.execute("DELETE FROM equipment")
    conn.commit()
    conn.close()
    initialize_database()
    return jsonify({"message": "Demo data reset"})

@app.route("/api/users")
@admin_required
def get_users():
    conn = get_connection()
    rows = conn.execute("SELECT id,username,full_name,role,active,created_at FROM users ORDER BY id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/users/add", methods=["POST"])
@admin_required
def add_user():
    data = request.get_json(silent=True) or request.form
    username = str(data.get("username", "")).strip()
    full_name = str(data.get("full_name", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", "user"))
    if not username or not full_name or len(password) < 6 or role not in ("admin", "user"):
        return jsonify({"error": "Enter all fields; password must be at least 6 characters."}), 400
    conn = get_connection()
    try:
        conn.execute("INSERT INTO users (username,password_hash,role,full_name) VALUES (?,?,?,?)",
                     (username, generate_password_hash(password), role, full_name))
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({"error": "Username already exists."}), 409
    conn.close()
    return jsonify({"message": "User created successfully"})

@app.route("/api/users/<int:user_id>/toggle", methods=["POST"])
@admin_required
def toggle_user(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "You cannot deactivate your own account."}), 400
    conn = get_connection()
    user = conn.execute("SELECT active FROM users WHERE id=?", (user_id,)).fetchone()
    if not user:
        conn.close(); return jsonify({"error":"User not found."}), 404
    conn.execute("UPDATE users SET active=? WHERE id=?", (0 if user["active"] else 1, user_id))
    conn.commit(); conn.close()
    return jsonify({"message":"Account status updated"})

@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    if user_id == session.get("user_id"):
        return jsonify({"error": "You cannot delete your own account."}), 400
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit(); conn.close()
    return jsonify({"message":"User deleted"})

@app.route("/api/users/<int:user_id>/password", methods=["POST"])
@admin_required
def change_password(user_id):
    data = request.get_json(silent=True) or request.form
    password = str(data.get("password", ""))
    if len(password) < 6:
        return jsonify({"error":"Password must be at least 6 characters."}), 400
    conn = get_connection()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (generate_password_hash(password), user_id))
    conn.commit(); conn.close()
    return jsonify({"message":"Password updated"})

if __name__ == "__main__":
    app.run(debug=True)
