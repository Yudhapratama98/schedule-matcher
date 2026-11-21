from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from scheduler.db import get_connection

# ==================== STUDENTS ====================

def list_students(status: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT s.*, 
               p.name as pembimbing_name, p.code as pembimbing_code,
               p1.name as penguji1_name, p1.code as penguji1_code,
               p2.name as penguji2_preset_name, p2.code as penguji2_preset_code
        FROM students s
        JOIN lecturers p ON s.pembimbing_id = p.id
        JOIN lecturers p1 ON s.penguji1_id = p1.id
        LEFT JOIN lecturers p2 ON s.penguji2_preset_id = p2.id
    """
    params = []
    if status:
        query += " WHERE s.status = ?"
        params.append(status)
    query += " ORDER BY s.id ASC;"
    cur.execute(query, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def get_student(student_id: int) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, 
               p.name as pembimbing_name, p.code as pembimbing_code,
               p1.name as penguji1_name, p1.code as penguji1_code,
               p2.name as penguji2_preset_name, p2.code as penguji2_preset_code
        FROM students s
        JOIN lecturers p ON s.pembimbing_id = p.id
        JOIN lecturers p1 ON s.penguji1_id = p1.id
        LEFT JOIN lecturers p2 ON s.penguji2_preset_id = p2.id
        WHERE s.id = ?;
    """, (student_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def create_student(
    name: str,
    nim: str,
    bidang: str,
    pembimbing_id: int,
    penguji1_id: int,
    penguji2_preset_id: Optional[int] = None,
    status: str = "eligible",
    notes: str = ""
) -> int:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO students (name, nim, bidang, pembimbing_id, penguji1_id, penguji2_preset_id, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """, (name.strip(), nim.strip(), bidang.strip() or "PWK", pembimbing_id, penguji1_id, penguji2_preset_id, status, notes.strip()))
        new_id = cur.lastrowid
    conn.close()
    return new_id

def update_student(
    student_id: int,
    name: str,
    nim: str,
    bidang: str,
    pembimbing_id: int,
    penguji1_id: int,
    penguji2_preset_id: Optional[int] = None,
    status: str = "eligible",
    notes: str = ""
) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE students
            SET name = ?, nim = ?, bidang = ?, pembimbing_id = ?, penguji1_id = ?,
                penguji2_preset_id = ?, status = ?, notes = ?
            WHERE id = ?;
        """, (name.strip(), nim.strip(), bidang.strip() or "PWK", pembimbing_id, penguji1_id, penguji2_preset_id, status, notes.strip(), student_id))
        updated = cur.rowcount > 0
    conn.close()
    return updated

def delete_student(student_id: int) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM students WHERE id = ?;", (student_id,))
        deleted = cur.rowcount > 0
    conn.close()
    return deleted

# ==================== LECTURERS ====================

def list_lecturers() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lecturers ORDER BY id ASC;")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def create_lecturer(code: str, name: str) -> int:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("INSERT INTO lecturers (code, name, is_active) VALUES (?, ?, 1);", (code.strip().upper(), name.strip()))
        new_id = cur.lastrowid
    conn.close()
    return new_id

def update_lecturer(lecturer_id: int, code: str, name: str, is_active: bool = True) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("UPDATE lecturers SET code = ?, name = ?, is_active = ? WHERE id = ?;", (code.strip().upper(), name.strip(), 1 if is_active else 0, lecturer_id))
        updated = cur.rowcount > 0
    conn.close()
    return updated

def delete_lecturer(lecturer_id: int) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM lecturers WHERE id = ?;", (lecturer_id,))
        deleted = cur.rowcount > 0
    conn.close()
    return deleted

# ==================== EXAM DAYS & SESSIONS ====================

def list_exam_days() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM exam_days ORDER BY sort_order ASC, date_iso ASC;")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def create_exam_day(date_iso: str, day_label: str) -> int:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM exam_days;")
        count = cur.fetchone()[0]
        cur.execute("INSERT INTO exam_days (date_iso, day_label, sort_order) VALUES (?, ?, ?);", (date_iso.strip(), day_label.strip(), count))
        new_id = cur.lastrowid
    conn.close()
    return new_id

def delete_exam_day(exam_day_id: int) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM exam_days WHERE id = ?;", (exam_day_id,))
        deleted = cur.rowcount > 0
    conn.close()
    return deleted

def list_sessions() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions ORDER BY session_num ASC;")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def update_session(session_num: int, time_range: str) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("UPDATE sessions SET time_range = ? WHERE session_num = ?;", (time_range.strip(), session_num))
        updated = cur.rowcount > 0
    conn.close()
    return updated

# ==================== LECTURER BLOCKS ====================

def list_blocks() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT b.*, l.name as lecturer_name, l.code as lecturer_code,
               d.date_iso, d.day_label
        FROM lecturer_blocks b
        JOIN lecturers l ON b.lecturer_id = l.id
        JOIN exam_days d ON b.exam_day_id = d.id
        ORDER BY b.exam_day_id ASC, b.session_num ASC, l.id ASC;
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def toggle_block(lecturer_id: int, exam_day_id: int, session_num: int, blocked: bool, reason: str = "") -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        if blocked:
            cur.execute("""
                INSERT OR REPLACE INTO lecturer_blocks (lecturer_id, exam_day_id, session_num, reason)
                VALUES (?, ?, ?, ?);
            """, (lecturer_id, exam_day_id, session_num, reason.strip()))
        else:
            cur.execute("""
                DELETE FROM lecturer_blocks
                WHERE lecturer_id = ? AND exam_day_id = ? AND session_num = ?;
            """, (lecturer_id, exam_day_id, session_num))
    conn.close()
    return True

# ==================== SETTINGS ====================

def get_settings() -> Dict[str, str]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM app_settings;")
    res = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return res

def update_setting(key: str, value: str) -> None:
    conn = get_connection()
    with conn:
        conn.execute("INSERT OR REPLACE INTO app_settings (key, value) VALUES (?, ?);", (key, value))
    conn.close()

# ==================== SCHEDULE ASSIGNMENTS & LIVE CONFLICT VALIDATOR ====================

def get_active_schedule() -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.id as assignment_id, a.student_id, a.exam_day_id, a.session_num, a.room_num,
               a.penguji2_id, a.is_locked, a.updated_at,
               s.name as student_name, s.nim, s.bidang, s.pembimbing_id, s.penguji1_id,
               p.name as pembimbing_name, p.code as pembimbing_code,
               p1.name as penguji1_name, p1.code as penguji1_code,
               p2.name as penguji2_name, p2.code as penguji2_code,
               d.date_iso, d.day_label,
               sess.time_range
        FROM schedule_assignments a
        JOIN students s ON a.student_id = s.id
        JOIN lecturers p ON s.pembimbing_id = p.id
        JOIN lecturers p1 ON s.penguji1_id = p1.id
        JOIN lecturers p2 ON a.penguji2_id = p2.id
        JOIN exam_days d ON a.exam_day_id = d.id
        JOIN sessions sess ON a.session_num = sess.session_num
        ORDER BY d.sort_order ASC, a.session_num ASC, a.room_num ASC;
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows

def validate_conflicts() -> List[Dict[str, Any]]:
    """
    Scans all schedule_assignments in SQLite and returns active conflicts:
    - LECTURER_DOUBLE_BOOKED: A lecturer appears more than once in the same (day, session).
    - LECTURER_BLOCKED: A lecturer is scheduled in a session where they are unavailable.
    - SAME_EXAMINER: Penguji 2 is the same person as Pembimbing or Penguji 1.
    - ROOM_COLLISION: Two students share the exact same (day, session, room).
    """
    assignments = get_active_schedule()
    blocks = list_blocks()
    blocked_set = {(b["lecturer_id"], b["exam_day_id"], b["session_num"]): b.get("reason", "") for b in blocks}

    conflicts: List[Dict[str, Any]] = []

    # 1. Check double bookings & room collisions per (day, session)
    slot_groups = defaultdict(list)
    for a in assignments:
        key = (a["exam_day_id"], a["session_num"])
        slot_groups[key].append(a)

    for (day_id, s_num), group in slot_groups.items():
        lecturer_appearances = defaultdict(list)
        room_appearances = defaultdict(list)

        for a in group:
            room_appearances[a["room_num"]].append(a)

            # Record presence for all 3 examiners
            lecturer_appearances[a["pembimbing_id"]].append((a, "Pembimbing"))
            lecturer_appearances[a["penguji1_id"]].append((a, "Penguji 1"))
            lecturer_appearances[a["penguji2_id"]].append((a, "Penguji 2"))

        # Check room collision
        for r_num, r_assignments in room_appearances.items():
            if len(r_assignments) > 1:
                conflicts.append({
                    "type": "ROOM_COLLISION",
                    "severity": "error",
                    "exam_day_id": day_id,
                    "session_num": s_num,
                    "room_num": r_num,
                    "date_iso": r_assignments[0]["date_iso"],
                    "day_label": r_assignments[0]["day_label"],
                    "message": f"Ruang {r_num} dipakai ganda oleh {len(r_assignments)} mahasiswa pada {r_assignments[0]['day_label']}, Sesi {s_num} ({r_assignments[0]['time_range']}).",
                    "students": [a["student_name"] for a in r_assignments]
                })

        # Check lecturer double booking
        for l_id, appearances in lecturer_appearances.items():
            if len(appearances) > 1:
                lecturer_name = appearances[0][0]["pembimbing_name"] if appearances[0][1] == "Pembimbing" else (
                    appearances[0][0]["penguji1_name"] if appearances[0][1] == "Penguji 1" else appearances[0][0]["penguji2_name"]
                )
                conflicts.append({
                    "type": "LECTURER_DOUBLE_BOOKED",
                    "severity": "error",
                    "lecturer_id": l_id,
                    "lecturer_name": lecturer_name,
                    "exam_day_id": day_id,
                    "session_num": s_num,
                    "date_iso": appearances[0][0]["date_iso"],
                    "day_label": appearances[0][0]["day_label"],
                    "message": f"Dosen '{lecturer_name}' terjadwal pada {len(appearances)} sidang sekaligus pada {appearances[0][0]['day_label']}, Sesi {s_num}.",
                    "students": [f"{app[0]['student_name']} ({app[1]})" for app in appearances]
                })

    # 2. Check blocked availability and examiner distinctness
    for a in assignments:
        # Same examiner check
        if a["penguji2_id"] == a["pembimbing_id"]:
            conflicts.append({
                "type": "SAME_EXAMINER",
                "severity": "error",
                "student_id": a["student_id"],
                "student_name": a["student_name"],
                "message": f"Mahasiswa '{a['student_name']}': Penguji 2 sama dengan Pembimbing ({a['penguji2_name']})."
            })
        if a["penguji2_id"] == a["penguji1_id"]:
            conflicts.append({
                "type": "SAME_EXAMINER",
                "severity": "error",
                "student_id": a["student_id"],
                "student_name": a["student_name"],
                "message": f"Mahasiswa '{a['student_name']}': Penguji 2 sama dengan Penguji 1 ({a['penguji2_name']})."
            })

        # Blocked availability check
        for role, l_id, l_name in [
            ("Pembimbing", a["pembimbing_id"], a["pembimbing_name"]),
            ("Penguji 1", a["penguji1_id"], a["penguji1_name"]),
            ("Penguji 2", a["penguji2_id"], a["penguji2_name"]),
        ]:
            if (l_id, a["exam_day_id"], a["session_num"]) in blocked_set:
                reason = blocked_set[(l_id, a["exam_day_id"], a["session_num"])]
                reason_str = f" (Alasan: {reason})" if reason else ""
                conflicts.append({
                    "type": "LECTURER_BLOCKED",
                    "severity": "warning",
                    "student_id": a["student_id"],
                    "student_name": a["student_name"],
                    "lecturer_id": l_id,
                    "lecturer_name": l_name,
                    "role": role,
                    "message": f"{role} '{l_name}' pada sidang '{a['student_name']}' berhalangan di {a['day_label']}, Sesi {a['session_num']}{reason_str}."
                })

    return conflicts

def update_assignment(
    student_id: int,
    exam_day_id: int,
    session_num: int,
    room_num: int,
    penguji2_id: int,
    is_locked: bool = True
) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO schedule_assignments (student_id, exam_day_id, session_num, room_num, penguji2_id, is_locked)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id) DO UPDATE SET
                exam_day_id = excluded.exam_day_id,
                session_num = excluded.session_num,
                room_num = excluded.room_num,
                penguji2_id = excluded.penguji2_id,
                is_locked = excluded.is_locked,
                updated_at = CURRENT_TIMESTAMP;
        """, (student_id, exam_day_id, session_num, room_num, penguji2_id, 1 if is_locked else 0))
    conn.close()
    return True

def delete_assignment(student_id: int) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM schedule_assignments WHERE student_id = ?;", (student_id,))
        deleted = cur.rowcount > 0
    conn.close()
    return deleted

def set_assignment_lock(student_id: int, is_locked: bool) -> bool:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE schedule_assignments SET is_locked = ?, updated_at = CURRENT_TIMESTAMP WHERE student_id = ?;",
            (1 if is_locked else 0, student_id)
        )
        updated = cur.rowcount > 0
    conn.close()
    return updated

def bulk_set_lock(
    is_locked: bool,
    exam_day_id: Optional[int] = None,
    session_num: Optional[int] = None
) -> int:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        query = "UPDATE schedule_assignments SET is_locked = ?, updated_at = CURRENT_TIMESTAMP WHERE 1=1"
        params: List[Any] = [1 if is_locked else 0]
        if exam_day_id is not None:
            query += " AND exam_day_id = ?"
            params.append(exam_day_id)
        if session_num is not None:
            query += " AND session_num = ?"
            params.append(session_num)
        cur.execute(query + ";", params)
        count = cur.rowcount
    conn.close()
    return count

def clear_schedule(unlocked_only: bool = True) -> int:
    conn = get_connection()
    with conn:
        cur = conn.cursor()
        if unlocked_only:
            cur.execute("DELETE FROM schedule_assignments WHERE is_locked = 0;")
        else:
            cur.execute("DELETE FROM schedule_assignments;")
        deleted = cur.rowcount
    conn.close()
    return deleted
