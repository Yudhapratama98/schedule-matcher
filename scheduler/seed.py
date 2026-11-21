from io import BytesIO
import re
from typing import Optional, Union, Dict, Any
import openpyxl

from scheduler.db import get_connection, init_db
from scheduler.parser import (
    normalize_text,
    to_date_obj,
    parse_blocked_sessions_text,
    match_dosen
)
from scheduler.models import Dosen

def _load_wb(path_or_bytes: Union[str, bytes]) -> openpyxl.Workbook:
    src = BytesIO(path_or_bytes) if isinstance(path_or_bytes, bytes) else path_or_bytes
    return openpyxl.load_workbook(src, data_only=True)

def seed_database_from_xlsx(
    master_path_or_bytes: Union[str, bytes],
    berhalangan_path_or_bytes: Union[str, bytes],
    db_path: Optional[str] = None,
    reset: bool = False
) -> Dict[str, Any]:
    init_db(db_path) if db_path else init_db()
    conn = get_connection(db_path) if db_path else get_connection()

    if reset:
        with conn:
            conn.executescript("""
                DELETE FROM schedule_assignments;
                DELETE FROM lecturer_blocks;
                DELETE FROM students;
                DELETE FROM exam_days;
                DELETE FROM lecturers;
            """)

    wb_m = _load_wb(master_path_or_bytes)
    if 'Dosen' not in wb_m.sheetnames or 'Mahasiswa' not in wb_m.sheetnames or 'Jadwal' not in wb_m.sheetnames:
        conn.close()
        raise ValueError("File master.xlsx harus memiliki sheet 'Dosen', 'Mahasiswa', dan 'Jadwal'.")

    # 1. Seed lecturers
    ws_d = wb_m['Dosen']
    dosen_map = {}
    dosen_by_id = {}
    with conn:
        for r in range(2, ws_d.max_row + 1):
            k = ws_d.cell(r, 1).value
            n = ws_d.cell(r, 2).value
            if k is not None and n is not None:
                try:
                    d_id = int(k)
                except ValueError:
                    continue
                name_str = str(n).strip()
                m_code = re.search(r'\((.*?)\)', name_str)
                code = m_code.group(1).strip() if m_code else f"D{d_id}"
                conn.execute(
                    "INSERT OR REPLACE INTO lecturers (id, code, name, is_active) VALUES (?, ?, ?, 1);",
                    (d_id, code, name_str)
                )
                d_obj = Dosen(id=d_id, name=name_str, code=code)
                dosen_map[normalize_text(name_str)] = d_obj
                dosen_by_id[d_id] = d_obj

    # 2. Seed exam days from Jadwal sheet (stop if date jumps backward)
    ws_j = wb_m['Jadwal']
    exam_days = [] # (date_iso, day_label, sort_order, start_row)
    last_date = None
    r = 6
    while r <= ws_j.max_row:
        u_val = ws_j.cell(r, 3).value
        if u_val is None:
            break
        h1 = ws_j.cell(r, 1).value
        h2 = ws_j.cell(r + 1, 1).value

        dt = to_date_obj(h1) or to_date_obj(h2)
        day_str = str(h1).strip() if h1 and not to_date_obj(h1) else (str(h2).strip() if h2 and not to_date_obj(h2) else "Hari")

        if dt:
            dt_iso = dt.strftime('%Y-%m-%d')
            if last_date and dt_iso < last_date:
                break
            if not any(d[0] == dt_iso for d in exam_days):
                exam_days.append((dt_iso, day_str, len(exam_days), r))
                last_date = dt_iso
        r += 20 # 4 sessions * 5 rows = 20 rows per day

    day_id_map = {}
    with conn:
        for dt_iso, day_label, s_order, _ in exam_days:
            conn.execute(
                "INSERT OR IGNORE INTO exam_days (date_iso, day_label, sort_order) VALUES (?, ?, ?);",
                (dt_iso, day_label, s_order)
            )
            cur = conn.cursor()
            cur.execute("SELECT id FROM exam_days WHERE date_iso = ?;", (dt_iso,))
            row = cur.fetchone()
            if row:
                day_id_map[dt_iso] = row[0]

    # 3. Seed lecturer blocks from berhalangan
    wb_b = _load_wb(berhalangan_path_or_bytes)
    ws_b = wb_b.active

    b_cols = []
    for c in range(3, ws_b.max_column + 1):
        d_val = ws_b.cell(5, c).value
        d_date = to_date_obj(d_val)
        if d_date:
            b_cols.append((c, d_date.strftime('%Y-%m-%d')))

    exam_day_list = sorted(exam_days, key=lambda x: x[2])
    col_to_exam_day_id = {}
    for i, (c, b_date_str) in enumerate(b_cols):
        if b_date_str in day_id_map:
            col_to_exam_day_id[c] = day_id_map[b_date_str]
        elif i < len(exam_day_list):
            fallback_iso = exam_day_list[i][0]
            col_to_exam_day_id[c] = day_id_map[fallback_iso]

    with conn:
        for r in range(6, ws_b.max_row + 1):
            nama_cell = ws_b.cell(r, 2).value
            if not nama_cell:
                continue
            d_obj = match_dosen(str(nama_cell), dosen_map)
            if not d_obj:
                continue

            for col_idx, _ in b_cols:
                cell_val = ws_b.cell(r, col_idx).value
                if not cell_val:
                    continue
                blocked_sess, _ = parse_blocked_sessions_text(str(cell_val))
                target_day_id = col_to_exam_day_id.get(col_idx)
                if target_day_id:
                    for s_num in blocked_sess:
                        conn.execute("""
                            INSERT OR IGNORE INTO lecturer_blocks (lecturer_id, exam_day_id, session_num, reason)
                            VALUES (?, ?, ?, ?);
                        """, (d_obj.id, target_day_id, s_num, str(cell_val).strip()))

    # 4. Seed students
    ws_m = wb_m['Mahasiswa']
    student_count = 0
    eligible_ids = set()
    with conn:
        for r in range(2, ws_m.max_row + 1):
            k = ws_m.cell(r, 1).value
            nama = ws_m.cell(r, 2).value
            nim = ws_m.cell(r, 3).value
            bidang = ws_m.cell(r, 4).value
            pemb = ws_m.cell(r, 5).value
            peng1 = ws_m.cell(r, 6).value
            peng2 = ws_m.cell(r, 8).value
            status_cell = ws_m.cell(r, 10).value

            if not k or not nama:
                continue
            try:
                s_id = int(k)
            except ValueError:
                continue

            pemb_obj = match_dosen(str(pemb) if pemb else None, dosen_map)
            peng1_obj = match_dosen(str(peng1) if peng1 else None, dosen_map)
            peng2_obj = match_dosen(str(peng2) if peng2 else None, dosen_map)
            if not pemb_obj or not peng1_obj:
                continue

            status_str = str(status_cell).strip().lower() if status_cell else ""
            is_eligible = status_str.startswith("aman")
            status_db = "eligible" if is_eligible else "postponed"
            if is_eligible:
                eligible_ids.add(s_id)

            conn.execute("""
                INSERT OR REPLACE INTO students (
                    id, name, nim, bidang, pembimbing_id, penguji1_id, penguji2_preset_id, status, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                s_id,
                str(nama).strip(),
                str(nim).strip() if nim is not None else "",
                str(bidang).strip() if bidang else "PWK",
                pemb_obj.id,
                peng1_obj.id,
                peng2_obj.id if peng2_obj else None,
                status_db,
                str(status_cell).strip() if status_cell else ""
            ))
            student_count += 1

    # 5. Seed existing Jadwal rows as LOCKED assignments (is_locked = 1)
    locked_seeded = 0
    seen_students = set()
    if exam_days:
        max_jadwal_row = exam_days[-1][3] + 19
        with conn:
            for r in range(6, max_jadwal_row + 1):
                mhs_val = ws_j.cell(r, 16).value
                dos_val = ws_j.cell(r, 17).value
                if mhs_val is None or dos_val is None:
                    continue
                try:
                    st_id = int(mhs_val)
                    p2_id = int(dos_val)
                except ValueError:
                    continue

                if st_id in seen_students or st_id not in eligible_ids or p2_id not in dosen_by_id:
                    continue

                offset = r - 6
                day_idx = offset // 20
                sess_num = ((offset % 20) // 5) + 1
                room_num = (offset % 5) + 1

                if day_idx < len(exam_days):
                    dt_iso = exam_days[day_idx][0]
                    day_id = day_id_map.get(dt_iso)
                    if day_id:
                        conn.execute("""
                            INSERT OR REPLACE INTO schedule_assignments
                            (student_id, exam_day_id, session_num, room_num, penguji2_id, is_locked)
                            VALUES (?, ?, ?, ?, ?, 1);
                        """, (st_id, day_id, sess_num, room_num, p2_id))
                        seen_students.add(st_id)
                        locked_seeded += 1

    conn.close()
    return {
        "lecturers_seeded": len(dosen_map),
        "days_seeded": len(exam_days),
        "students_seeded": student_count,
        "locked_assignments_seeded": locked_seeded
    }
