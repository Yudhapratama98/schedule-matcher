import time
from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict
from ortools.sat.python import cp_model

from scheduler.db import get_connection
from scheduler.crud import (
    list_students, list_lecturers, list_exam_days, list_sessions,
    list_blocks, get_settings, get_active_schedule, validate_conflicts
)

def run_db_scheduler(
    respect_locked: bool = True,
    auto_assign_p2: bool = True
) -> Dict[str, Any]:
    start_time = time.time()

    students = list_students(status="eligible")
    lecturers = list_lecturers()
    days = list_exam_days()
    sessions = list_sessions()
    blocks = list_blocks()
    settings = get_settings()

    max_rooms = int(settings.get("max_rooms_per_slot", "5"))

    if not students:
        raise ValueError("Tidak ada mahasiswa berstatus 'eligible' (layak) untuk dijadwalkan.")
    if not days:
        raise ValueError("Tidak ada hari pelaksanaan sidang yang terdaftar.")
    if not sessions:
        raise ValueError("Tidak ada sesi sidang yang terdaftar.")

    # Flatten (day, session) pairs
    sess_list: List[Dict[str, Any]] = []
    day_sess_to_idx: Dict[Tuple[int, int], int] = {}
    for d_idx, d in enumerate(days):
        for s in sessions:
            idx = len(sess_list)
            sess_list.append({
                "idx": idx,
                "exam_day_id": d["id"],
                "session_num": s["session_num"],
                "day_idx": d_idx,
                "day_label": d["day_label"],
                "date_iso": d["date_iso"],
                "time_range": s["time_range"]
            })
            day_sess_to_idx[(d["id"], s["session_num"])] = idx

    num_students = len(students)
    num_sessions = len(sess_list)
    dosen_ids = [l["id"] for l in lecturers]
    dosen_by_id = {l["id"]: l for l in lecturers}
    blocked_set = {(b["lecturer_id"], b["exam_day_id"], b["session_num"]) for b in blocks}

    # Fetch existing locked assignments if respect_locked is True
    existing_assignments = {a["student_id"]: a for a in get_active_schedule()}
    locked_students = {}
    if respect_locked:
        for st_id, a in existing_assignments.items():
            if a.get("is_locked"):
                locked_students[st_id] = a

    # 1. Pre-check feasibility for each student
    for st in students:
        if st["id"] in locked_students:
            continue
        pemb_id = st["pembimbing_id"]
        peng1_id = st["penguji1_id"]
        valid_sess_count = 0
        for s in sess_list:
            if (pemb_id, s["exam_day_id"], s["session_num"]) in blocked_set:
                continue
            if (peng1_id, s["exam_day_id"], s["session_num"]) in blocked_set:
                continue
            if not auto_assign_p2 and st.get("penguji2_preset_id"):
                if (st["penguji2_preset_id"], s["exam_day_id"], s["session_num"]) in blocked_set:
                    continue
            valid_sess_count += 1

        if valid_sess_count == 0:
            pemb_name = dosen_by_id[pemb_id]["name"] if pemb_id in dosen_by_id else f"ID {pemb_id}"
            peng1_name = dosen_by_id[peng1_id]["name"] if peng1_id in dosen_by_id else f"ID {peng1_id}"
            raise ValueError(
                f"Mahasiswa '{st['name']}' tidak dapat dijadwalkan: "
                f"Pembimbing ({pemb_name}) dan Penguji 1 ({peng1_name}) "
                f"tidak memiliki sesi bersamaan yang bebas dari jadwal berhalangan."
            )

    # 2. Formulate CP-SAT Model
    model = cp_model.CpModel()

    # x[m, s]
    x = {}
    for m in range(num_students):
        st = students[m]
        st_id = st["id"]
        is_locked = st_id in locked_students
        locked_info = locked_students.get(st_id)

        for s in range(num_sessions):
            x[m, s] = model.NewBoolVar(f"x_{m}_{s}")

        model.AddExactlyOne(x[m, s] for s in range(num_sessions))

        # Enforce locked slot if applicable
        if is_locked and locked_info:
            target_key = (locked_info["exam_day_id"], locked_info["session_num"])
            if target_key in day_sess_to_idx:
                locked_s_idx = day_sess_to_idx[target_key]
                model.Add(x[m, locked_s_idx] == 1)

    # y[m, d]
    y = {}
    for m in range(num_students):
        st = students[m]
        st_id = st["id"]
        is_locked = st_id in locked_students
        locked_info = locked_students.get(st_id)

        for d in dosen_ids:
            y[m, d] = model.NewBoolVar(f"y_{m}_{d}")
        model.AddExactlyOne(y[m, d] for d in dosen_ids)

        if is_locked and locked_info and locked_info.get("penguji2_id"):
            model.Add(y[m, locked_info["penguji2_id"]] == 1)
        elif not auto_assign_p2 and st.get("penguji2_preset_id") and st["penguji2_preset_id"] in dosen_by_id:
            model.Add(y[m, st["penguji2_preset_id"]] == 1)
        else:
            model.Add(y[m, st["pembimbing_id"]] == 0)
            model.Add(y[m, st["penguji1_id"]] == 0)

    # Room capacity constraint per session (respecting locked students)
    for s in range(num_sessions):
        locked_in_s = sum(1 for m in range(num_students) if students[m]["id"] in locked_students and day_sess_to_idx.get((locked_students[students[m]["id"]]["exam_day_id"], locked_students[students[m]["id"]]["session_num"])) == s)
        unlocked_in_s = [x[m, s] for m in range(num_students) if students[m]["id"] not in locked_students]
        if unlocked_in_s:
            remaining_cap = max(0, max_rooms - locked_in_s)
            model.Add(sum(unlocked_in_s) <= remaining_cap)

    # Lecturer conflict constraint (locked students never crash solver; unlocked students never clash)
    for s in range(num_sessions):
        s_obj = sess_list[s]
        d_id = s_obj["exam_day_id"]
        s_num = s_obj["session_num"]

        for l_id in dosen_ids:
            is_blocked = (l_id, d_id, s_num) in blocked_set
            locked_uses = 0
            unlocked_involved = []

            for m in range(num_students):
                st = students[m]
                st_id = st["id"]
                if st_id in locked_students:
                    l_info = locked_students[st_id]
                    if day_sess_to_idx.get((l_info["exam_day_id"], l_info["session_num"])) == s:
                        if st["pembimbing_id"] == l_id or st["penguji1_id"] == l_id or l_info.get("penguji2_id") == l_id:
                            locked_uses += 1
                    continue

                if st["pembimbing_id"] == l_id or st["penguji1_id"] == l_id:
                    if is_blocked or locked_uses > 0:
                        model.Add(x[m, s] == 0)
                    else:
                        unlocked_involved.append(x[m, s])
                else:
                    p2_in_s = model.NewBoolVar(f"p2_{m}_{l_id}_{s}")
                    model.AddBoolAnd([x[m, s], y[m, l_id]]).OnlyEnforceIf(p2_in_s)
                    model.AddBoolOr([x[m, s].Not(), y[m, l_id].Not()]).OnlyEnforceIf(p2_in_s.Not())
                    if is_blocked or locked_uses > 0:
                        model.Add(p2_in_s == 0)
                    else:
                        unlocked_involved.append(p2_in_s)

            if unlocked_involved:
                if locked_uses > 0:
                    model.Add(sum(unlocked_involved) == 0)
                else:
                    model.Add(sum(unlocked_involved) <= 1)

    # Workload balance objective
    p2_counts = []
    for l_id in dosen_ids:
        c = model.NewIntVar(0, num_students, f"cnt_{l_id}")
        model.Add(c == sum(y[m, l_id] for m in range(num_students)))
        p2_counts.append(c)

    max_p2 = model.NewIntVar(0, num_students, "max_p2")
    min_p2 = model.NewIntVar(0, num_students, "min_p2")
    model.AddMaxEquality(max_p2, p2_counts)
    model.AddMinEquality(min_p2, p2_counts)

    model.Minimize(max_p2 - min_p2)

    # 3. Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 4.0
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(
            "Tidak ditemukan jadwal yang memenuhi semua syarat tanpa bentrok. "
            "Coba ubah opsi Penguji 2 menjadi 'Otomatis seimbangkan' "
            "atau buka kunci sidang yang sebelumnya dikunci manual."
        )

    # 4. Save results to database
    conn = get_connection()
    with conn:
        # Group students by assigned session
        session_students = defaultdict(list)
        for m in range(num_students):
            for s in range(num_sessions):
                if solver.Value(x[m, s]) == 1:
                    session_students[s].append(m)
                    break

        new_assignments = []
        for s, m_list in session_students.items():
            s_obj = sess_list[s]
            used_rooms = set()

            # First, preserve locked room numbers
            for m_idx in m_list:
                st = students[m_idx]
                if st["id"] in locked_students:
                    r_num = locked_students[st["id"]]["room_num"]
                    used_rooms.add(r_num)

            # Next, assign available room numbers to unlocked students
            available_rooms = [r for r in range(1, max_rooms + 1) if r not in used_rooms]
            room_ptr = 0

            for m_idx in m_list:
                st = students[m_idx]
                st_id = st["id"]
                assigned_p2 = None
                for l_id in dosen_ids:
                    if solver.Value(y[m_idx, l_id]) == 1:
                        assigned_p2 = l_id
                        break

                if st_id in locked_students:
                    assigned_room = locked_students[st_id]["room_num"]
                    is_lock = 1
                else:
                    assigned_room = available_rooms[room_ptr] if room_ptr < len(available_rooms) else (room_ptr + 1)
                    room_ptr += 1
                    is_lock = 0

                new_assignments.append((
                    st_id,
                    s_obj["exam_day_id"],
                    s_obj["session_num"],
                    assigned_room,
                    assigned_p2,
                    is_lock
                ))

        # Clear and write back
        cur = conn.cursor()
        cur.execute("DELETE FROM schedule_assignments;")
        cur.executemany("""
            INSERT INTO schedule_assignments (student_id, exam_day_id, session_num, room_num, penguji2_id, is_locked)
            VALUES (?, ?, ?, ?, ?, ?);
        """, new_assignments)

    conn.close()

    elapsed_ms = round((time.time() - start_time) * 1000, 1)
    active_sched = get_active_schedule()
    conflicts = validate_conflicts()

    return {
        "scheduled_students": len(active_sched),
        "total_eligible_students": num_students,
        "solve_time_ms": elapsed_ms,
        "conflicts_count": len(conflicts),
        "conflicts": conflicts,
        "schedule": active_sched
    }
