from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import os
import joblib
import numpy as np

app = Flask(__name__)
app.secret_key = "smart_hospital_emergency_secure_key_2026"

DATABASE = "hospital.db"
MODEL_PATH = "triage_model.pkl"

# Check if model file is in root or inside .vscode
if not os.path.exists(MODEL_PATH) and os.path.exists(os.path.join(".vscode", MODEL_PATH)):
    MODEL_PATH = os.path.join(".vscode", MODEL_PATH)

ml_model = None
if os.path.exists(MODEL_PATH):
    try:
        ml_model = joblib.load(MODEL_PATH)
    except Exception as e:
        print("Model loading notice:", e)

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def create_database():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT UNIQUE,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            phone TEXT,
            address TEXT,
            blood_group TEXT,
            emergency_contact TEXT,
            medical_history TEXT,
            allergies TEXT,
            status TEXT DEFAULT 'Waiting',
            created_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS triage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            priority TEXT,
            confidence REAL,
            symptoms TEXT,
            heart_rate TEXT,
            oxygen_level TEXT,
            temperature TEXT,
            blood_pressure TEXT,
            respiratory_rate TEXT,
            assessment_reason TEXT,
            status TEXT DEFAULT 'Waiting',
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

# -----------------------------
# STAFF AUTHENTICATION
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username == "admin" and password == "admin123":
            session["user"] = username
            return redirect(url_for("dashboard"))
        else:
            error = "Invalid Staff Username or Password."
    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# -----------------------------
# MAIN COMMAND CENTER DASHBOARD
# -----------------------------
@app.route("/")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM patients")
    total_patients = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM triage_history WHERE priority='RED' OR priority='CRITICAL'")
    critical_cases = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM triage_history WHERE priority='YELLOW' OR priority='HIGH'")
    high_cases = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM triage_history WHERE priority='GREEN' OR priority='MODERATE'")
    moderate_cases = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM triage_history WHERE priority='BLACK' OR priority='LOW'")
    low_cases = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM patients ORDER BY id DESC LIMIT 5")
    recent_patients = cursor.fetchall()
    conn.close()

    return render_template(
        "dashboard.html",
        total_patients=total_patients,
        critical_cases=critical_cases,
        high_cases=high_cases,
        moderate_cases=moderate_cases,
        low_cases=low_cases,
        recent_patients=recent_patients
    )

# -----------------------------
# PATIENT REGISTRATION
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        name = request.form.get("name")
        age = request.form.get("age")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        address = request.form.get("address")
        blood_group = request.form.get("blood_group")
        emergency_contact = request.form.get("emergency_contact")
        medical_history = request.form.get("medical_history")
        allergies = request.form.get("allergies")

        conn = get_db()
        cursor = conn.cursor()

        year = datetime.now().year
        cursor.execute("SELECT COUNT(*) FROM patients")
        next_count = cursor.fetchone()[0] + 1
        patient_id = f"P-{year}-{next_count:04d}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO patients 
            (patient_id, name, age, gender, phone, address, blood_group, emergency_contact, medical_history, allergies, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Waiting', ?)
        """, (patient_id, name, age, gender, phone, address, blood_group, emergency_contact, medical_history, allergies, created_at))

        conn.commit()
        conn.close()
        return redirect(url_for("patient_details", patient_id=patient_id))

    return render_template("register.html")

# -----------------------------
# PATIENTS DIRECTORY
# -----------------------------
@app.route("/patients")
def patients():
    if "user" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "")
    conn = get_db()
    cursor = conn.cursor()

    if search:
        cursor.execute("""
            SELECT * FROM patients 
            WHERE patient_id LIKE ? OR name LIKE ? OR phone LIKE ? 
            ORDER BY id DESC
        """, (f"%{search}%", f"%{search}%", f"%{search}%"))
    else:
        cursor.execute("SELECT * FROM patients ORDER BY id DESC")

    patients_list = cursor.fetchall()
    conn.close()
    return render_template("patients.html", patients=patients_list, search=search)

# -----------------------------
# PATIENT PROFILE
# -----------------------------
@app.route("/patient/<patient_id>")
def patient_details(patient_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,))
    patient = cursor.fetchone()

    cursor.execute("SELECT * FROM triage_history WHERE patient_id=? ORDER BY id DESC", (patient_id,))
    history = cursor.fetchall()
    conn.close()

    if patient is None:
        return "Patient not found", 404

    return render_template("patient_details.html", patient=patient, history=history)

# -----------------------------
# UPDATE PATIENT RECORD
# -----------------------------
@app.route("/update/<patient_id>", methods=["GET", "POST"])
def update_patient(patient_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name")
        age = request.form.get("age")
        gender = request.form.get("gender")
        phone = request.form.get("phone")
        address = request.form.get("address")
        blood_group = request.form.get("blood_group")
        emergency_contact = request.form.get("emergency_contact")
        medical_history = request.form.get("medical_history")
        allergies = request.form.get("allergies")

        cursor.execute("""
            UPDATE patients SET
                name=?, age=?, gender=?, phone=?, address=?,
                blood_group=?, emergency_contact=?, medical_history=?, allergies=?
            WHERE patient_id=?
        """, (name, age, gender, phone, address, blood_group, emergency_contact, medical_history, allergies, patient_id))

        conn.commit()
        conn.close()
        return redirect(url_for("patient_details", patient_id=patient_id))

    cursor.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,))
    patient = cursor.fetchone()
    conn.close()
    return render_template("update.html", patient=patient)

# -----------------------------
# DELETE PATIENT
# -----------------------------
@app.route("/delete/<patient_id>", methods=["POST"])
def delete_patient(patient_id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM patients WHERE patient_id=?", (patient_id,))
    cursor.execute("DELETE FROM triage_history WHERE patient_id=?", (patient_id,))
    conn.commit()
    conn.close()

    return redirect(url_for("patients"))

# -----------------------------
# AI EMERGENCY TRIAGE (MoHFW / DGHS PROTOCOL)
# -----------------------------
@app.route("/triage", methods=["GET", "POST"])
def triage():
    if "user" not in session:
        return redirect(url_for("login"))

    result = None
    if request.method == "POST":
        patient_id = request.form.get("patient_id")
        emergency_category = request.form.get("emergency_category") or "Medical Emergencies"
        primary_incident = request.form.get("primary_incident") or "Heart Attack / Chest Pain"

        emergency_type_map = {
            "chest_pain": 0, "respiratory": 1, "stroke": 2, "rta": 3,
            "burns": 4, "snake_bite": 5, "poisoning": 6, "pregnancy": 7,
            "dehydration": 8, "disaster": 9
        }
        emer_key = request.form.get("emergency_type_code") or "chest_pain"
        emergency_type_num = emergency_type_map.get(emer_key, 0)

        spo2 = float(request.form.get("oxygen_level") or 98.0)
        heart_rate = float(request.form.get("heart_rate") or 72.0)
        temperature = float(request.form.get("temperature") or 37.0)
        resp_rate = float(request.form.get("respiratory_rate") or 16.0)

        bp_raw = request.form.get("blood_pressure") or "120/80"
        try:
            systolic_bp = float(bp_raw.split("/")[0])
        except Exception:
            systolic_bp = 120.0

        unconscious = 1 if request.form.get("unconscious") else 0
        heavy_bleeding = 1 if request.form.get("heavy_bleeding") else 0
        severe_pain = 1 if request.form.get("severe_pain") else 0
        respiratory_distress = 1 if request.form.get("respiratory_distress") else 0

        feature_vector = np.array([[
            spo2, heart_rate, temperature, resp_rate, systolic_bp,
            emergency_type_num, unconscious, heavy_bleeding, severe_pain, respiratory_distress
        ]])

        confidence = 92.0
        priority = "YELLOW"
        if ml_model:
            try:
                priority = ml_model.predict(feature_vector)[0]
                probabilities = ml_model.predict_proba(feature_vector)[0]
                confidence = round(float(np.max(probabilities)) * 100, 1)
            except Exception:
                # Fallback rule engine if feature vector size changes
                if unconscious == 1 or spo2 < 88 or systolic_bp < 80 or emer_key == "snake_bite":
                    priority = "RED"
                elif respiratory_distress == 1 or heavy_bleeding == 1 or spo2 < 93:
                    priority = "YELLOW"
                else:
                    priority = "GREEN"

        # MoHFW / DGHS Clinical Explainable Reasoning
        reasons = []
        if priority == "BLACK":
            reasons.append("NDMA Mass-Casualty Protocol: Unresponsive / Expectant Category")
        if unconscious == 1:
            reasons.append("Immediate Resuscitation Required: Patient is unconscious / GCS severely low")
        if emer_key == "snake_bite":
            reasons.append("National Protocol: Suspected Venomous Envenomation (Anti-Snake Venom ASV Protocol)")
        if emer_key == "pregnancy" and systolic_bp >= 160:
            reasons.append("Maternal Hypertensive Crisis: Impending Eclampsia Seizure Risk")
        if emer_key == "stroke":
            reasons.append("Golden Hour Stroke Window: Acute Neurological Deficit (FAST Protocol)")
        if heavy_bleeding == 1:
            reasons.append("Active Massive Hemorrhage: Impending Hypovolemic Shock")
        if spo2 < 90:
            reasons.append(f"Severe Hypoxemic Respiratory Failure (SpO₂: {spo2}%)")
        elif spo2 < 94:
            reasons.append(f"Suboptimal Oxygen Saturation (SpO₂: {spo2}%)")
        if systolic_bp < 90:
            reasons.append(f"Clinical Hypotension / Septic-Circulatory Shock (Systolic BP: {int(systolic_bp)} mmHg)")
        if heart_rate > 130:
            reasons.append(f"Marked Tachycardia / Acute Cardiovascular Stress ({int(heart_rate)} BPM)")
        if temperature >= 40.0:
            reasons.append(f"Severe Hyperpyrexia / Heat Stroke Alert ({temperature}°C)")

        if not reasons:
            reasons.append("Physiological vitals stable; patient placed in routine clinical stream.")

        symptoms_str = f"[{emergency_category}] {primary_incident}"
        reason_str = "; ".join(reasons)
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO triage_history 
            (patient_id, priority, confidence, symptoms, heart_rate, oxygen_level, temperature, blood_pressure, respiratory_rate, assessment_reason, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Waiting', ?)
        """, (patient_id, priority, confidence, symptoms_str, str(heart_rate), str(spo2), str(temperature), bp_raw, str(resp_rate), reason_str, created_at))
        conn.commit()
        conn.close()

        result = {
            "patient_id": patient_id,
            "category": emergency_category,
            "incident": primary_incident,
            "priority": priority,
            "confidence": confidence,
            "reasons": reasons
        }

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT patient_id, name FROM patients ORDER BY id DESC")
    patients_list = cursor.fetchall()
    conn.close()

    return render_template("triage.html", result=result, patients=patients_list)

# -----------------------------
# SMART EMERGENCY QUEUE (MoHFW: RED -> YELLOW -> GREEN -> BLACK)
# -----------------------------
@app.route("/queue")
def queue():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT triage_history.*, patients.name, patients.age, patients.gender
        FROM triage_history
        JOIN patients ON triage_history.patient_id = patients.patient_id
        ORDER BY 
            CASE triage_history.priority
                WHEN 'RED' THEN 1
                WHEN 'CRITICAL' THEN 1
                WHEN 'YELLOW' THEN 2
                WHEN 'HIGH' THEN 2
                WHEN 'GREEN' THEN 3
                WHEN 'MODERATE' THEN 3
                WHEN 'BLACK' THEN 4
                ELSE 5
            END,
            triage_history.id DESC
    """)
    queue_list = cursor.fetchall()
    conn.close()
    return render_template("queue.html", queue=queue_list)

# -----------------------------
# UPDATE QUEUE STATUS
# -----------------------------
@app.route("/update_status/<int:triage_id>", methods=["POST"])
def update_status(triage_id):
    if "user" not in session:
        return redirect(url_for("login"))

    new_status = request.form.get("status")
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE triage_history SET status=? WHERE id=?", (new_status, triage_id))
    conn.commit()
    conn.close()
    return redirect(url_for("queue"))

# -----------------------------
# TRIAGE HISTORY LOGS
# -----------------------------
@app.route("/history")
def history():
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT triage_history.*, patients.name 
        FROM triage_history 
        LEFT JOIN patients ON triage_history.patient_id = patients.patient_id 
        ORDER BY triage_history.id DESC
    """)
    history_list = cursor.fetchall()
    conn.close()
    return render_template("history.html", history=history_list)

if __name__ == "__main__":
    create_database()
    app.run(debug=True)