import sqlite3
import os
import sys
from typing import Optional, Dict, Any, List

def get_default_db_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~/.local/share")
        app_dir = os.path.join(base, "ScheduleMatcher")
        os.makedirs(app_dir, exist_ok=True)
        return os.path.join(app_dir, "schedule.db")
    return os.path.join(os.getcwd(), "schedule.db")

DB_PATH = get_default_db_path()

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn

def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS lecturers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS exam_days (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_iso TEXT NOT NULL UNIQUE,
            day_label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sessions (
            session_num INTEGER PRIMARY KEY,
            time_range TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS lecturer_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lecturer_id INTEGER NOT NULL REFERENCES lecturers(id) ON DELETE CASCADE,
            exam_day_id INTEGER NOT NULL REFERENCES exam_days(id) ON DELETE CASCADE,
            session_num INTEGER NOT NULL REFERENCES sessions(session_num) ON DELETE CASCADE,
            reason TEXT DEFAULT '',
            UNIQUE(lecturer_id, exam_day_id, session_num)
        );

        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            nim TEXT DEFAULT '',
            bidang TEXT DEFAULT 'PWK',
            pembimbing_id INTEGER NOT NULL REFERENCES lecturers(id),
            penguji1_id INTEGER NOT NULL REFERENCES lecturers(id),
            penguji2_preset_id INTEGER REFERENCES lecturers(id),
            status TEXT NOT NULL DEFAULT 'eligible', -- 'eligible' or 'postponed'
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS schedule_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL UNIQUE REFERENCES students(id) ON DELETE CASCADE,
            exam_day_id INTEGER NOT NULL REFERENCES exam_days(id),
            session_num INTEGER NOT NULL REFERENCES sessions(session_num),
            room_num INTEGER NOT NULL,
            penguji2_id INTEGER NOT NULL REFERENCES lecturers(id),
            is_locked INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        """)

        # Default standard sessions
        default_sessions = [
            (1, "08.00-09.30"),
            (2, "10.00-11.30"),
            (3, "13.30-15.00"),
            (4, "16.00-17.30"),
        ]
        for s_num, t_range in default_sessions:
            conn.execute(
                "INSERT OR IGNORE INTO sessions (session_num, time_range) VALUES (?, ?);",
                (s_num, t_range)
            )

        # Default settings
        conn.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('max_rooms_per_slot', '5');")
        conn.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('p2_mode', 'auto');")
        conn.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('institution_name', 'Program Studi Perencanaan Wilayah dan Kota - ITK');")
        conn.execute("INSERT OR IGNORE INTO app_settings (key, value) VALUES ('room_names', 'Ruang Sidang 1, Ruang Sidang 2, Ruang Sidang 3, Ruang Sidang 4, Ruang Sidang 5');")

    conn.close()

def is_db_empty(db_path: str = DB_PATH) -> bool:
    if not os.path.exists(db_path):
        return True
    conn = get_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM students;")
    count = cur.fetchone()[0]
    conn.close()
    return count == 0
