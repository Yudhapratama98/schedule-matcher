import os
import io
import pytest
import openpyxl
from starlette.testclient import TestClient

from app import app
from scheduler.parser import load_master_and_berhalangan
from scheduler.solver import solve_schedule
from scheduler.exporter import export_schedule_to_excel

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MASTER_PATH = os.path.join(TEST_DATA_DIR, "master.xlsx")
BERHALANGAN_PATH = os.path.join(TEST_DATA_DIR, "berhalangan.xlsx")

def test_real_data_schedule_and_export():
    assert os.path.exists(MASTER_PATH)
    assert os.path.exists(BERHALANGAN_PATH)

    with open(MASTER_PATH, "rb") as f:
        master_bytes = f.read()
    with open(BERHALANGAN_PATH, "rb") as f:
        berhalangan_bytes = f.read()

    students, dosen_list, sessions, blocked_slots, warnings = load_master_and_berhalangan(
        master_bytes, berhalangan_bytes
    )

    assert len(students) == 46
    assert len(dosen_list) == 16
    assert len(sessions) > 0

    # Solve with auto_assign_p2=True (workload balance)
    res_auto = solve_schedule(
        students=students,
        dosen_list=dosen_list,
        sessions=sessions,
        blocked_slots=blocked_slots,
        auto_assign_p2=True,
        max_rooms_per_slot=5,
        warnings=warnings
    )

    assert res_auto.scheduled_count == 46
    assert res_auto.solve_time_ms < 5000 # Under 5 seconds

    # Check for NO clashes in any session
    for s_idx in range(len(sessions)):
        assignments_in_s = [a for a in res_auto.assignments if a.session_idx == s_idx]
        assert len(assignments_in_s) <= 5

        lecturers_in_s = []
        for a in assignments_in_s:
            lecturers_in_s.append(a.pembimbing_id)
            lecturers_in_s.append(a.penguji1_id)
            lecturers_in_s.append(a.penguji2_id)
            # Ensure penguji2 distinct
            assert a.penguji2_id != a.pembimbing_id
            assert a.penguji2_id != a.penguji1_id

        # No double booking in this session
        assert len(lecturers_in_s) == len(set(lecturers_in_s))

    # Test export
    exported_bytes = export_schedule_to_excel(master_bytes, res_auto.assignments)
    assert len(exported_bytes) > 0

    wb_exp = openpyxl.load_workbook(io.BytesIO(exported_bytes), data_only=False)
    ws_exp = wb_exp['Jadwal']
    populated_rows = [r for r in range(6, 200) if ws_exp.cell(r, 16).value is not None]
    assert len(populated_rows) == 46

def test_fastapi_endpoints():
    with open(MASTER_PATH, "rb") as f:
        master_bytes = f.read()
    with open(BERHALANGAN_PATH, "rb") as f:
        berhalangan_bytes = f.read()

    client = TestClient(app)

    # Health check
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"

    # Schedule post
    files = {
        "master_file": ("master.xlsx", master_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "berhalangan_file": ("berhalangan.xlsx", berhalangan_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }
    data = {
        "auto_assign_penguji2": "true",
        "max_rooms_per_slot": "5"
    }
    res_sched = client.post("/api/schedule", files=files, data=data)
    assert res_sched.status_code == 200
    json_data = res_sched.json()
    assert json_data["summary"]["scheduled_students"] == 46
    file_id = json_data["file_id"]

    # Download get
    res_dl = client.get(f"/api/schedule/download/{file_id}")
    assert res_dl.status_code == 200
    assert len(res_dl.content) > 0

    # Config get (reads .env defaults)
    res_cfg = client.get("/api/config")
    assert res_cfg.status_code == 200
    cfg_json = res_cfg.json()
    assert "master_url" in cfg_json

    # Test sync endpoint without credentials returns requires_credentials gracefully
    res_sync = client.post("/api/schedule/sync-google-sheet", data={"file_id": file_id})
    assert res_sync.status_code == 200
    sync_json = res_sync.json()
    assert sync_json.get("requires_credentials") is True or sync_json.get("success") is True
