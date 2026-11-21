import os
import io
import pytest
import openpyxl
from starlette.testclient import TestClient

from app import app
from scheduler.db import init_db
from scheduler.seed import seed_database_from_xlsx
from scheduler.crud import (
    list_students, list_lecturers, list_exam_days,
    get_active_schedule, validate_conflicts, update_assignment
)
from scheduler.db_solver import run_db_scheduler
from scheduler.db_exporter import export_db_schedule_to_excel

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MASTER_PATH = os.path.join(TEST_DATA_DIR, "master.xlsx")
BERHALANGAN_PATH = os.path.join(TEST_DATA_DIR, "berhalangan.xlsx")

def test_sqlite_seeding_and_crud():
    # 1. Test Seed (including locked assignments from Jadwal sheet)
    res = seed_database_from_xlsx(MASTER_PATH, BERHALANGAN_PATH, reset=True)
    assert res["lecturers_seeded"] == 16
    assert res["days_seeded"] == 8
    assert res["students_seeded"] >= 52
    assert res["locked_assignments_seeded"] == 52

    students = list_students(status="eligible")
    assert len(students) == 52

    lecturers = list_lecturers()
    assert len(lecturers) == 16

    days = list_exam_days()
    assert len(days) == 8

    # Verify seeded schedule is locked by default
    seeded_sched = get_active_schedule()
    assert len(seeded_sched) == 52
    assert all(a["is_locked"] == 1 for a in seeded_sched)

def test_db_scheduler_and_export():
    # 2. Test Auto-scheduler (full re-optimization with respect_locked=False -> 0 conflicts)
    res = run_db_scheduler(respect_locked=False, auto_assign_p2=True)
    assert res["scheduled_students"] == 52
    assert res["conflicts_count"] == 0

    schedule = get_active_schedule()
    assert len(schedule) == 52

    # Verify no double booking in any session
    session_lecturers = {}
    for a in schedule:
        key = (a["exam_day_id"], a["session_num"])
        if key not in session_lecturers:
            session_lecturers[key] = []
        l_list = [a["pembimbing_id"], a["penguji1_id"], a["penguji2_id"]]
        # Distinctness
        assert a["penguji2_id"] != a["pembimbing_id"]
        assert a["penguji2_id"] != a["penguji1_id"]
        session_lecturers[key].extend(l_list)

    for key, l_list in session_lecturers.items():
        assert len(l_list) == len(set(l_list))

    # Test Excel Export
    xlsx_bytes = export_db_schedule_to_excel()
    assert len(xlsx_bytes) > 0

    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), data_only=True)
    assert "Jadwal Ujian" in wb.sheetnames
    assert "Beban Dosen" in wb.sheetnames
    ws_j = wb["Jadwal Ujian"]
    assert ws_j.max_row == 55 # row 1 title, row 3 header, rows 4..55 = 52 students

def test_live_conflict_detection_and_lock():
    # Get first 2 students
    schedule = get_active_schedule()
    st1 = schedule[0]
    st2 = schedule[1]

    # Deliberately move st2 into st1's exact same day, session, and room
    # To test ROOM_COLLISION and live conflict detection
    update_assignment(
        student_id=st2["student_id"],
        exam_day_id=st1["exam_day_id"],
        session_num=st1["session_num"],
        room_num=st1["room_num"],
        penguji2_id=st1["pembimbing_id"], # Also trigger SAME_EXAMINER or collision
        is_locked=True
    )

    conflicts = validate_conflicts()
    assert len(conflicts) > 0
    conflict_types = {c["type"] for c in conflicts}
    assert "ROOM_COLLISION" in conflict_types

    # Re-run scheduler with respect_locked=False to resolve all
    res = run_db_scheduler(respect_locked=False, auto_assign_p2=True)
    assert res["conflicts_count"] == 0

def test_fastapi_rest_endpoints():
    client = TestClient(app)

    # Health
    r = client.get("/api/health")
    assert r.status_code == 200

    # Get schedule
    r = client.get("/api/schedule")
    assert r.status_code == 200
    data = r.json()
    assert data["scheduled_count"] == 52

    # Get students
    r = client.get("/api/students")
    assert r.status_code == 200
    assert len(r.json()) >= 52

    # Toggle block
    days = list_exam_days()
    day_id = days[0]["id"]
    r = client.post("/api/blocks/toggle", json={
        "lecturer_id": 1,
        "exam_day_id": day_id,
        "session_num": 1,
        "blocked": True,
        "reason": "Test Block"
    })
    assert r.status_code == 200

    # Export
    r = client.get("/api/schedule/export")
    assert r.status_code == 200
    assert len(r.content) > 0

    # 1-click lock toggle & bulk lock
    first_st_id = data["schedule"][0]["student_id"]
    r = client.patch(f"/api/schedule/assignments/{first_st_id}/lock", json={"is_locked": True})
    assert r.status_code == 200
    assert r.json()["is_locked"] is True

    r = client.post("/api/schedule/lock-bulk", json={"is_locked": False})
    assert r.status_code == 200
    assert r.json()["updated_count"] >= 52

    # Backup DB
    r = client.get("/api/backup-db")
    assert r.status_code == 200
    assert len(r.content) > 0

def test_requirements_include_testclient_deps():
    req_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "requirements.txt")
    with open(req_path, "r", encoding="utf-8") as f:
        reqs = f.read().lower()
    assert "httpx>=" in reqs
    assert "starlette>=0.27.0,<1.0.0" in reqs
