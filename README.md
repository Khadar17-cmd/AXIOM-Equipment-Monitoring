# AXIOM — IoT & AI-Enabled Skill Training Equipment Monitoring

A Flask + SQLite college project prototype for monitoring training equipment. The application includes login and role-based access, equipment monitoring, rule-based health scores, simulated IoT readings, image-upload demonstration, alerts, analytics, CSV export, user management, equipment registration, a project knowledge assistant, and optional SMTP email alerts.

## 1. Requirements
- Windows 10/11, Linux or macOS
- Python 3.9+
- A modern browser

## 2. Run on Windows
1. Extract the ZIP file.
2. Open the extracted `IoT_AI_Equipment_Monitoring_Enhanced_Features` folder.
3. Click the folder address bar, type `cmd`, and press Enter.
4. Run:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

5. Open `http://127.0.0.1:5000` in your browser.

If `python` is not recognized, try `py` in place of `python`.

## 3. Demo login
- Admin: `admin` / `admin123`
- User: `user` / `user123`

Change demo passwords before any deployment outside a local demonstration. Admin can register equipment and manage users. Users can view monitoring pages but cannot change simulated equipment readings or administer accounts.

## 4. New modules
- **Register Equipment:** Admin can add a machine with name, category, location, initial condition and notes. New machines appear in equipment monitoring and analytics.
- **Maintenance Assistant:** A project knowledge assistant that answers questions using current equipment records and built-in rule-based guidance. It is not connected to an external generative AI service.
- **Email Notifications:** Admin can add recipient email addresses. Warning and Critical transitions from sensor simulation or fault simulation create alert records and attempt email delivery when SMTP is configured. Duplicate email attempts for the same equipment/status are limited to once per 30 minutes.

## 5. Optional real email delivery
Email sending is disabled until SMTP settings are supplied. For Gmail, enable 2-Step Verification and create a Google App Password; do not use your normal Gmail password. Set these environment variables in the same terminal before running the app:

PowerShell example:

```powershell
$env:SMTP_HOST="smtp.gmail.com"
$env:SMTP_PORT="587"
$env:SMTP_USER="your-email@gmail.com"
$env:SMTP_PASSWORD="your-google-app-password"
$env:SMTP_FROM="your-email@gmail.com"
python app.py
```

The notification page shows whether the required SMTP values are present. If SMTP is not configured, the application records the alert but cannot send an email. Email sending also requires an internet connection and a provider that permits SMTP access.

## 6. Technical notes and honest prototype limitations
- **IoT readings are simulated in Python.** No physical sensors, microcontrollers or real IoT gateway are connected in this version.
- **AI image detection is a filename-based demonstration.** It previews uploaded images but does not perform actual visual recognition or use YOLO.
- **Maintenance Assistant is rule-based.** It reads current SQLite equipment values and returns predefined diagnostic guidance; it is not a trained LLM.
- **Health score is rule-based**, not a predictive machine-learning score.
- **Email alerts require SMTP configuration** and at least one recipient added by an admin.
- The dashboard, equipment, alerts and analytics pages refresh their displayed data periodically.

## 7. Project structure

```text
IoT_AI_Equipment_Monitoring_Enhanced_Features/
├── app.py
├── database.py
├── equipment.db
├── requirements.txt
├── README.md
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── equipment.html
│   ├── add_equipment.html
│   ├── ai_detection.html
│   ├── chatbot.html
│   ├── alerts.html
│   ├── notifications.html
│   ├── analytics.html
│   └── users.html
└── static/
    ├── css/style.css
    ├── js/dashboard.js
    └── uploads/
```

The application applies additive SQLite schema migrations at startup, so the existing database gains the additional equipment fields and notification tables without deleting the current equipment or user records.
