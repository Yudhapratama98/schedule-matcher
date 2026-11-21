import os
import sys
import webbrowser
import threading
from typing import Dict, Any, Optional, List
from collections import defaultdict

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, Body
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from scheduler.db import init_db, is_db_empty, DB_PATH
from scheduler.seed import seed_database_from_xlsx
from scheduler.crud import (
    list_students, get_student, create_student, update_student, delete_student,
    list_lecturers, create_lecturer, update_lecturer, delete_lecturer,
    list_exam_days, create_exam_day, delete_exam_day,
    list_sessions, update_session,
    list_blocks, toggle_block,
    get_settings, update_setting,
    get_active_schedule, validate_conflicts,
    update_assignment, delete_assignment, clear_schedule,
    set_assignment_lock, bulk_set_lock
)
from scheduler.db_solver import run_db_scheduler
from scheduler.db_exporter import export_db_schedule_to_excel

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = getattr(sys, '_MEIPASS')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Initialize database
init_db()

# Auto-seed if database is empty and seed files exist
if is_db_empty():
    seed_master = os.path.join(BASE_DIR, "tests", "data", "master.xlsx")
    seed_berh = os.path.join(BASE_DIR, "tests", "data", "berhalangan.xlsx")
    if os.path.exists(seed_master) and os.path.exists(seed_berh):
        try:
            seed_database_from_xlsx(seed_master, seed_berh)
        except Exception as e:
            print(f"Warning: Initial seeding failed: {e}")

app = FastAPI(title="Sistem Penjadwalan Sidang Skripsi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h3>Aplikasi Penjadwalan Sidang Skripsi</h3>")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

# ==================== SCHEDULE & CONFLICTS ====================

@app.get("/api/schedule")
async def get_schedule():
    schedule = get_active_schedule()
    conflicts = validate_conflicts()
    lecturers = list_lecturers()

    p1_p2_counts = defaultdict(int)
    p3_counts = defaultdict(int)
    for a in schedule:
        p1_p2_counts[a["pembimbing_id"]] += 1
        p1_p2_counts[a["penguji1_id"]] += 1
        p3_counts[a["penguji2_id"]] += 1

    workload = []
    for l in lecturers:
        p1_2 = p1_p2_counts[l["id"]]
        p3 = p3_counts[l["id"]]
        workload.append({
            "dosen_id": l["id"],
            "nama": l["name"],
            "code": l["code"],
            "p1_p2_count": p1_2,
            "p3_count": p3,
            "total": p1_2 + p3
        })

    eligible_count = len(list_students(status="eligible"))

    return {
        "scheduled_count": len(schedule),
        "total_eligible_students": eligible_count,
        "conflicts_count": len(conflicts),
        "conflicts": conflicts,
        "schedule": schedule,
        "lecturer_workload": workload
    }

@app.post("/api/schedule/generate")
async def generate_schedule(
    respect_locked: bool = Form(True),
    auto_assign_penguji2: bool = Form(True)
):
    try:
        res = run_db_scheduler(
            respect_locked=respect_locked,
            auto_assign_p2=auto_assign_penguji2
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan: {str(e)}")

@app.patch("/api/schedule/assignments/{student_id}")
async def patch_assignment(
    student_id: int,
    exam_day_id: int = Body(...),
    session_num: int = Body(...),
    room_num: int = Body(...),
    penguji2_id: int = Body(...),
    is_locked: bool = Body(True)
):
    update_assignment(
        student_id=student_id,
        exam_day_id=exam_day_id,
        session_num=session_num,
        room_num=room_num,
        penguji2_id=penguji2_id,
        is_locked=is_locked
    )
    conflicts = validate_conflicts()
    schedule = get_active_schedule()
    return {
        "success": True,
        "conflicts_count": len(conflicts),
        "conflicts": conflicts,
        "schedule": schedule
    }

@app.delete("/api/schedule/assignments/{student_id}")
async def remove_assignment(student_id: int):
    delete_assignment(student_id)
    return {"success": True, "conflicts": validate_conflicts()}

@app.patch("/api/schedule/assignments/{student_id}/lock")
async def lock_single_assignment(
    student_id: int,
    is_locked: bool = Body(..., embed=True)
):
    ok = set_assignment_lock(student_id, is_locked)
    if not ok:
        raise HTTPException(status_code=404, detail="Jadwal mahasiswa tidak ditemukan.")
    return {"success": True, "student_id": student_id, "is_locked": is_locked}

@app.post("/api/schedule/lock-bulk")
async def lock_bulk_assignments(
    is_locked: bool = Body(...),
    exam_day_id: Optional[int] = Body(None),
    session_num: Optional[int] = Body(None)
):
    count = bulk_set_lock(is_locked=is_locked, exam_day_id=exam_day_id, session_num=session_num)
    return {"success": True, "updated_count": count, "is_locked": is_locked}

@app.get("/api/schedule/export")
async def export_schedule():
    xlsx_bytes = export_db_schedule_to_excel()
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="jadwal_sidang_skripsi.xlsx"'}
    )

# ==================== STUDENTS (PENGAJUAN MAHASISWA) ====================

@app.get("/api/students")
async def api_list_students(status: Optional[str] = Query(None)):
    return list_students(status)

@app.get("/api/students/{student_id}")
async def api_get_student(student_id: int):
    st = get_student(student_id)
    if not st:
        raise HTTPException(status_code=404, detail="Mahasiswa tidak ditemukan.")
    return st

@app.post("/api/students")
async def api_create_student(
    name: str = Body(...),
    nim: str = Body(""),
    bidang: str = Body("PWK"),
    pembimbing_id: int = Body(...),
    penguji1_id: int = Body(...),
    penguji2_preset_id: Optional[int] = Body(None),
    status: str = Body("eligible"),
    notes: str = Body("")
):
    new_id = create_student(
        name=name,
        nim=nim,
        bidang=bidang,
        pembimbing_id=pembimbing_id,
        penguji1_id=penguji1_id,
        penguji2_preset_id=penguji2_preset_id,
        status=status,
        notes=notes
    )
    return {"success": True, "id": new_id}

@app.put("/api/students/{student_id}")
async def api_update_student(
    student_id: int,
    name: str = Body(...),
    nim: str = Body(""),
    bidang: str = Body("PWK"),
    pembimbing_id: int = Body(...),
    penguji1_id: int = Body(...),
    penguji2_preset_id: Optional[int] = Body(None),
    status: str = Body("eligible"),
    notes: str = Body("")
):
    ok = update_student(
        student_id=student_id,
        name=name,
        nim=nim,
        bidang=bidang,
        pembimbing_id=pembimbing_id,
        penguji1_id=penguji1_id,
        penguji2_preset_id=penguji2_preset_id,
        status=status,
        notes=notes
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Mahasiswa tidak ditemukan.")
    return {"success": True}

@app.delete("/api/students/{student_id}")
async def api_delete_student(student_id: int):
    delete_student(student_id)
    return {"success": True}

# ==================== LECTURERS & AVAILABILITY BLOCKS ====================

@app.get("/api/lecturers")
async def api_list_lecturers():
    return list_lecturers()

@app.post("/api/lecturers")
async def api_create_lecturer(
    code: str = Body(...),
    name: str = Body(...)
):
    new_id = create_lecturer(code=code, name=name)
    return {"success": True, "id": new_id}

@app.put("/api/lecturers/{lecturer_id}")
async def api_update_lecturer(
    lecturer_id: int,
    code: str = Body(...),
    name: str = Body(...),
    is_active: bool = Body(True)
):
    ok = update_lecturer(lecturer_id, code, name, is_active)
    if not ok:
        raise HTTPException(status_code=404, detail="Dosen tidak ditemukan.")
    return {"success": True}

@app.delete("/api/lecturers/{lecturer_id}")
async def api_delete_lecturer(lecturer_id: int):
    delete_lecturer(lecturer_id)
    return {"success": True}

@app.get("/api/blocks")
async def api_list_blocks():
    return list_blocks()

@app.post("/api/blocks/toggle")
async def api_toggle_block(
    lecturer_id: int = Body(...),
    exam_day_id: int = Body(...),
    session_num: int = Body(...),
    blocked: bool = Body(...),
    reason: str = Body("")
):
    toggle_block(lecturer_id, exam_day_id, session_num, blocked, reason)
    conflicts = validate_conflicts()
    return {"success": True, "conflicts": conflicts}

# ==================== EXAM DAYS & SETTINGS ====================

@app.get("/api/days")
async def api_list_days():
    return list_exam_days()

@app.post("/api/days")
async def api_create_day(
    date_iso: str = Body(...),
    day_label: str = Body(...)
):
    new_id = create_exam_day(date_iso, day_label)
    return {"success": True, "id": new_id}

@app.delete("/api/days/{day_id}")
async def api_delete_day(day_id: int):
    delete_exam_day(day_id)
    return {"success": True}

@app.get("/api/sessions")
async def api_list_sessions():
    return list_sessions()

@app.put("/api/sessions/{session_num}")
async def api_update_session(
    session_num: int,
    time_range: str = Body(..., embed=True)
):
    ok = update_session(session_num, time_range)
    if not ok:
        raise HTTPException(status_code=404, detail="Sesi tidak ditemukan.")
    return {"success": True}

@app.get("/api/settings")
async def api_get_settings():
    return get_settings()

@app.put("/api/settings")
async def api_update_settings(
    max_rooms_per_slot: str = Body(...),
    p2_mode: str = Body("auto"),
    institution_name: str = Body("Program Studi Perencanaan Wilayah dan Kota - ITK"),
    room_names: str = Body("Ruang Sidang 1, Ruang Sidang 2, Ruang Sidang 3, Ruang Sidang 4, Ruang Sidang 5")
):
    update_setting("max_rooms_per_slot", max_rooms_per_slot)
    update_setting("p2_mode", p2_mode)
    update_setting("institution_name", institution_name.strip())
    update_setting("room_names", room_names.strip())
    return {"success": True}

@app.post("/api/import-xlsx")
async def api_import_xlsx(
    master_file: UploadFile = File(...),
    berhalangan_file: UploadFile = File(...)
):
    try:
        m_bytes = await master_file.read()
        b_bytes = await berhalangan_file.read()
        res = seed_database_from_xlsx(m_bytes, b_bytes, reset=True)
        return {"success": True, "summary": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Gagal mengimpor Excel: {str(e)}")

@app.get("/api/backup-db")
async def api_backup_db():
    if not os.path.exists(DB_PATH):
        raise HTTPException(status_code=404, detail="Database tidak ditemukan.")
    with open(DB_PATH, "rb") as f:
        data = f.read()
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="schedule_backup.db"'}
    )

def start_server(port: int = 8000, open_browser: bool = True):
    # PyInstaller with console=False sets stdout/stderr to None on Windows, which crashes uvicorn's formatter
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_config=None)

if __name__ == "__main__":
    start_server()
