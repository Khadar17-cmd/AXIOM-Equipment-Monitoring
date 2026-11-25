import sqlite3
from werkzeug.security import generate_password_hash

DATABASE = "equipment.db"

def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            temperature REAL DEFAULT 0,
            vibration REAL DEFAULT 0,
            power REAL DEFAULT 0,
            usage_hours REAL DEFAULT 0,
            last_maintenance TEXT
        )
    """)

    # Additive schema migrations keep existing project databases compatible.
    equipment_columns = {row[1] for row in cursor.execute("PRAGMA table_info(equipment)").fetchall()}
    for column, definition in [("category", "TEXT DEFAULT 'Training equipment'"), ("location", "TEXT DEFAULT ''"), ("description", "TEXT DEFAULT ''")]:
        if column not in equipment_columns:
            cursor.execute(f"ALTER TABLE equipment ADD COLUMN {column} {definition}")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_recipients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER, status TEXT NOT NULL, message TEXT NOT NULL,
            sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sensor_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_id INTEGER NOT NULL,
            temperature REAL DEFAULT 0,
            vibration REAL DEFAULT 0,
            power REAL DEFAULT 0,
            usage_hours REAL DEFAULT 0,
            status TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY(equipment_id) REFERENCES equipment(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            full_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        cursor.execute("""
            INSERT INTO users (username,password_hash,role,full_name)
            VALUES (?,?,?,?)
        """, ("admin", generate_password_hash("admin123"), "admin", "System Administrator"))
        cursor.execute("""
            INSERT INTO users (username,password_hash,role,full_name)
            VALUES (?,?,?,?)
        """, ("user", generate_password_hash("user123"), "user", "Training User"))

    count = cursor.execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    if count == 0:
        data = [
            ("CNC Machine", "Active", 38, 1.2, 4.5, 2.7, "2026-08-15"),
            ("Lathe Machine", "Active", 42, 1.8, 3.8, 3.2, "2026-08-10"),
            ("Welding Machine", "Warning", 71, 4.5, 5.2, 4.1, "2026-07-20"),
            ("Drilling Machine", "Offline", 0, 0, 0, 0, "2026-08-05"),
            ("Grinding Machine", "Active", 45, 2.1, 3.2, 2.4, "2026-08-12"),
            ("Milling Machine", "Active", 40, 1.5, 4.0, 3.1, "2026-08-18")
        ]
        cursor.executemany("""
            INSERT INTO equipment
            (name,status,temperature,vibration,power,usage_hours,last_maintenance)
            VALUES (?,?,?,?,?,?,?)
        """, data)

    history_count = cursor.execute("SELECT COUNT(*) FROM sensor_history").fetchone()[0]
    if history_count == 0:
        rows = cursor.execute("SELECT * FROM equipment").fetchall()
        for row in rows:
            cursor.execute("""
                INSERT INTO sensor_history
                (equipment_id, temperature, vibration, power, usage_hours, status, recorded_at)
                VALUES (?,?,?,?,?,?,datetime('now'))
            """, (row["id"], row["temperature"], row["vibration"], row["power"],
                  row["usage_hours"], row["status"]))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")
