import time
from typing import List, Set, Tuple, Dict, Optional
from ortools.sat.python import cp_model

from scheduler.models import (
    Student, Dosen, SessionSlot, ScheduleAssignment, ScheduleResult, ParserWarning
)

def solve_schedule(
    students: List[Student],
    dosen_list: List[Dosen],
    sessions: List[SessionSlot],
    blocked_slots: Set[Tuple[int, int, int]],
    auto_assign_p2: bool = False,
    max_rooms_per_slot: int = 5,
    warnings: Optional[List[ParserWarning]] = None
) -> ScheduleResult:
    start_time = time.time()
    warnings_list = warnings or []

    dosen_by_id = {d.id: d for d in dosen_list}
    num_students = len(students)
    num_sessions = len(sessions)
    num_dosen = len(dosen_list)
    dosen_ids = [d.id for d in dosen_list]

    if num_students == 0:
        return ScheduleResult(
            assignments=[],
            warnings=warnings_list,
            solve_time_ms=0.0,
            total_eligible=0,
            scheduled_count=0
        )

    if num_sessions * max_rooms_per_slot < num_students:
        raise ValueError(
            f"Kapasitas ruangan tidak mencukupi: Total slot tersedia adalah "
            f"{num_sessions * max_rooms_per_slot}, namun ada {num_students} mahasiswa."
        )

    # 1. Diagnostic pre-check: verify each student has at least 1 possible session
    for m in students:
        pemb = dosen_by_id.get(m.pembimbing_id)
        peng1 = dosen_by_id.get(m.penguji1_id)
        pemb_name = pemb.name if pemb else f"ID {m.pembimbing_id}"
        peng1_name = peng1.name if peng1 else f"ID {m.penguji1_id}"

        valid_sessions_count = 0
        for s in sessions:
            if (m.pembimbing_id, s.day_idx, s.session_num) in blocked_slots:
                continue
            if (m.penguji1_id, s.day_idx, s.session_num) in blocked_slots:
                continue
            if not auto_assign_p2 and m.penguji2_preset_id:
                if (m.penguji2_preset_id, s.day_idx, s.session_num) in blocked_slots:
                    continue
            valid_sessions_count += 1

        if valid_sessions_count == 0:
            if not auto_assign_p2 and m.penguji2_preset_id:
                p2 = dosen_by_id.get(m.penguji2_preset_id)
                p2_name = p2.name if p2 else f"ID {m.penguji2_preset_id}"
                raise ValueError(
                    f"Mahasiswa '{m.name}' tidak dapat dijadwalkan: "
                    f"Pembimbing ({pemb_name}), Penguji 1 ({peng1_name}), dan Penguji 2 ({p2_name}) "
                    f"tidak memiliki satupun sesi kosong yang bersamaan karena jadwal berhalangan."
                )
            else:
                raise ValueError(
                    f"Mahasiswa '{m.name}' tidak dapat dijadwalkan: "
                    f"Pembimbing ({pemb_name}) dan Penguji 1 ({peng1_name}) "
                    f"tidak memiliki satupun sesi kosong yang bersamaan karena jadwal berhalangan."
                )

    # 2. Build CP-SAT Model
    model = cp_model.CpModel()

    # x[m, s] == 1 iff student m is scheduled in session s
    x = {}
    for m in range(num_students):
        for s in range(num_sessions):
            x[m, s] = model.NewBoolVar(f"x_{m}_{s}")
        model.AddExactlyOne(x[m, s] for s in range(num_sessions))

    # y[m, d] == 1 iff lecturer d is Penguji 2 for student m
    y = {}
    for m in range(num_students):
        st = students[m]
        for d in dosen_ids:
            y[m, d] = model.NewBoolVar(f"y_{m}_{d}")
        model.AddExactlyOne(y[m, d] for d in dosen_ids)

        if not auto_assign_p2 and st.penguji2_preset_id and st.penguji2_preset_id in dosen_by_id:
            model.Add(y[m, st.penguji2_preset_id] == 1)
        else:
            # Penguji 2 cannot be Pembimbing or Penguji 1
            if st.pembimbing_id in dosen_by_id:
                model.Add(y[m, st.pembimbing_id] == 0)
            if st.penguji1_id in dosen_by_id:
                model.Add(y[m, st.penguji1_id] == 0)

    # Capacity per session
    for s in range(num_sessions):
        model.Add(sum(x[m, s] for m in range(num_students)) <= max_rooms_per_slot)

    # Lecturer conflict and availability
    for s in range(num_sessions):
        sess = sessions[s]
        s_day = sess.day_idx
        s_num = sess.session_num

        for d in dosen_ids:
            is_blocked = (d, s_day, s_num) in blocked_slots
            involved_vars = []

            for m in range(num_students):
                st = students[m]
                if st.pembimbing_id == d or st.penguji1_id == d:
                    if is_blocked:
                        model.Add(x[m, s] == 0)
                    involved_vars.append(x[m, s])
                else:
                    p2_in_s = model.NewBoolVar(f"p2_{m}_{d}_{s}")
                    model.AddBoolAnd([x[m, s], y[m, d]]).OnlyEnforceIf(p2_in_s)
                    model.AddBoolOr([x[m, s].Not(), y[m, d].Not()]).OnlyEnforceIf(p2_in_s.Not())
                    if is_blocked:
                        model.Add(p2_in_s == 0)
                    involved_vars.append(p2_in_s)

            # At most 1 defense per lecturer in each session
            model.Add(sum(involved_vars) <= 1)

    # Soft objective: Balance Penguji 2 workload across lecturers
    p2_counts = []
    for d in dosen_ids:
        c = model.NewIntVar(0, num_students, f"p2_cnt_{d}")
        model.Add(c == sum(y[m, d] for m in range(num_students)))
        p2_counts.append(c)

    max_p2 = model.NewIntVar(0, num_students, "max_p2")
    min_p2 = model.NewIntVar(0, num_students, "min_p2")
    model.AddMaxEquality(max_p2, p2_counts)
    model.AddMinEquality(min_p2, p2_counts)

    # Minimize workload spread
    model.Minimize(max_p2 - min_p2)

    # 3. Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError(
            "Tidak ditemukan jadwal yang memenuhi semua syarat tanpa bentrok. "
            "Coba ubah opsi Penguji 2 menjadi 'Otomatis pilih & seimbangkan' "
            "atau kurangi batasan berhalangan dosen."
        )

    # 4. Construct assignments
    assignments: List[ScheduleAssignment] = []

    # Group students by assigned session
    session_students: Dict[int, List[int]] = {s: [] for s in range(num_sessions)}
    for m in range(num_students):
        for s in range(num_sessions):
            if solver.Value(x[m, s]) == 1:
                session_students[s].append(m)
                break

    for s, m_indices in session_students.items():
        sess = sessions[s]
        for room_idx, m_idx in enumerate(m_indices):
            st = students[m_idx]
            assigned_p2_id = None
            for d in dosen_ids:
                if solver.Value(y[m_idx, d]) == 1:
                    assigned_p2_id = d
                    break

            pemb = dosen_by_id.get(st.pembimbing_id)
            peng1 = dosen_by_id.get(st.penguji1_id)
            peng2 = dosen_by_id.get(assigned_p2_id)

            row_num = sess.slot_rows[room_idx] if room_idx < len(sess.slot_rows) else (sess.slot_rows[0] + room_idx)
            urut = (s * max_rooms_per_slot) + (room_idx + 1)

            assignments.append(ScheduleAssignment(
                student_id=st.id,
                student_name=st.name,
                session_idx=s,
                day_name=sess.day_name,
                date_str=sess.date_str,
                session_num=sess.session_num,
                time_range=sess.time_range,
                row_num=row_num,
                urut=urut,
                pembimbing_id=st.pembimbing_id,
                pembimbing_name=pemb.name if pemb else "",
                penguji1_id=st.penguji1_id,
                penguji1_name=peng1.name if peng1 else "",
                penguji2_id=assigned_p2_id or 0,
                penguji2_name=peng2.name if peng2 else ""
            ))

    # Sort assignments by row_num
    assignments.sort(key=lambda a: a.row_num)

    elapsed_ms = round((time.time() - start_time) * 1000, 1)

    return ScheduleResult(
        assignments=assignments,
        warnings=warnings_list,
        solve_time_ms=elapsed_ms,
        total_eligible=num_students,
        scheduled_count=len(assignments)
    )
