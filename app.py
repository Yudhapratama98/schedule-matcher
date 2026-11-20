import os
import uuid
import sys
import json
import webbrowser
import threading
from typing import Dict, Any, Optional, List
from collections import defaultdict

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from scheduler.parser import load_master_and_berhalangan
from scheduler.solver import solve_schedule
from scheduler.exporter import export_schedule_to_excel
from scheduler.gsheets import fetch_google_sheet_as_xlsx, write_back_to_google_sheet, get_credentials

app = FastAPI(title="Sistem Penjadwalan Ujian Skripsi")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = getattr(sys, '_MEIPASS')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIR = os.path.join(BASE_DIR, "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory storage for generated schedules and binary files (max 10 recent)
SCHEDULE_CACHE: Dict[str, Dict[str, Any]] = {}

def get_env_defaults() -> Dict[str, str]:
    env_path = os.path.join(os.getcwd(), ".env")
    defaults = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    defaults[k.strip()] = v.strip().strip("\"'")
    return defaults

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h3>Aplikasi Penjadwalan Ujian Skripsi</h3>")

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/config")
async def get_config():
    env_dict = get_env_defaults()
    master_url = env_dict.get("MASTER_UJIAN_SIDANG_AKHIR_E2526_PWK_ITK", "")
    berhalangan_url = env_dict.get("JADWAL_BERHALANGAN_DOSEN", "")
    has_creds = get_credentials() is not None
    return {
        "master_url": master_url,
        "berhalangan_url": berhalangan_url,
        "has_google_credentials": has_creds
    }

@app.post("/api/schedule")
async def create_schedule(
    master_file: Optional[UploadFile] = File(None),
    berhalangan_file: Optional[UploadFile] = File(None),
    master_url: Optional[str] = Form(None),
    berhalangan_url: Optional[str] = Form(None),
    auto_assign_penguji2: bool = Form(False),
    max_rooms_per_slot: int = Form(5),
    credentials_json: Optional[str] = Form(None)
):
    try:
        master_bytes: Optional[bytes] = None
        berhalangan_bytes: Optional[bytes] = None

        # 1. Obtain master bytes (from file upload or Google Sheets URL)
        if master_file and master_file.filename:
            master_bytes = await master_file.read()
        elif master_url and master_url.strip():
            master_bytes = fetch_google_sheet_as_xlsx(master_url.strip(), credentials_json)
        else:
            env_dict = get_env_defaults()
            default_url = env_dict.get("MASTER_UJIAN_SIDANG_AKHIR_E2526_PWK_ITK")
            if default_url:
                master_bytes = fetch_google_sheet_as_xlsx(default_url, credentials_json)

        # 2. Obtain berhalangan bytes
        if berhalangan_file and berhalangan_file.filename:
            berhalangan_bytes = await berhalangan_file.read()
        elif berhalangan_url and berhalangan_url.strip():
            berhalangan_bytes = fetch_google_sheet_as_xlsx(berhalangan_url.strip(), credentials_json)
        else:
            env_dict = get_env_defaults()
            default_url = env_dict.get("JADWAL_BERHALANGAN_DOSEN")
            if default_url:
                berhalangan_bytes = fetch_google_sheet_as_xlsx(default_url, credentials_json)

        if not master_bytes:
            raise HTTPException(status_code=400, detail="Data master ujian tidak ditemukan (mohon unggah berkas atau masukkan link Google Sheet).")
        if not berhalangan_bytes:
            raise HTTPException(status_code=400, detail="Data jadwal berhalangan dosen tidak ditemukan.")

        students, dosen_list, sessions, blocked_slots, warnings = load_master_and_berhalangan(
            master_bytes, berhalangan_bytes
        )

        result = solve_schedule(
            students=students,
            dosen_list=dosen_list,
            sessions=sessions,
            blocked_slots=blocked_slots,
            auto_assign_p2=auto_assign_penguji2,
            max_rooms_per_slot=max_rooms_per_slot,
            warnings=warnings
        )

        # Export to excel binary for backup download
        output_xlsx_bytes = export_schedule_to_excel(master_bytes, result.assignments)

        file_id = str(uuid.uuid4())[:8]
        if len(SCHEDULE_CACHE) > 10:
            SCHEDULE_CACHE.pop(next(iter(SCHEDULE_CACHE)))

        SCHEDULE_CACHE[file_id] = {
            "bytes": output_xlsx_bytes,
            "assignments": result.assignments,
            "master_url": master_url or get_env_defaults().get("MASTER_UJIAN_SIDANG_AKHIR_E2526_PWK_ITK", "")
        }

        # Calculate lecturer workload summary
        p1_p2_counts = defaultdict(int)
        p3_counts = defaultdict(int)

        for a in result.assignments:
            p1_p2_counts[a.pembimbing_id] += 1
            p1_p2_counts[a.penguji1_id] += 1
            p3_counts[a.penguji2_id] += 1

        workload = []
        for d in dosen_list:
            p1_p2 = p1_p2_counts[d.id]
            p3 = p3_counts[d.id]
            workload.append({
                "dosen_id": d.id,
                "nama": d.name,
                "code": d.code,
                "p1_p2_count": p1_p2,
                "p3_count": p3,
                "total": p1_p2 + p3
            })

        workload.sort(key=lambda item: item["dosen_id"])

        schedule_items = []
        for a in result.assignments:
            schedule_items.append({
                "hari": a.day_name,
                "tanggal": a.date_str,
                "sesi": a.session_num,
                "waktu": a.time_range,
                "urut": a.urut,
                "row_num": a.row_num,
                "mhs_id": a.student_id,
                "mahasiswa": a.student_name,
                "pembimbing_id": a.pembimbing_id,
                "pembimbing": a.pembimbing_name,
                "penguji1_id": a.penguji1_id,
                "penguji_1": a.penguji1_name,
                "penguji2_id": a.penguji2_id,
                "penguji_2": a.penguji2_name
            })

        warnings_data = [
            {
                "source": w.source,
                "lecturer": w.lecturer,
                "raw_value": w.raw_value,
                "message": w.message
            }
            for w in result.warnings
        ]

        return {
            "file_id": file_id,
            "download_url": f"/api/schedule/download/{file_id}",
            "can_sync_gsheet": True,
            "master_url": SCHEDULE_CACHE[file_id]["master_url"],
            "summary": {
                "total_eligible_students": result.total_eligible,
                "scheduled_students": result.scheduled_count,
                "solve_time_ms": result.solve_time_ms
            },
            "warnings": warnings_data,
            "schedule": schedule_items,
            "lecturer_workload": workload
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan internal: {str(e)}")

@app.post("/api/schedule/sync-google-sheet")
async def sync_to_google_sheet(
    file_id: str = Form(...),
    master_url: Optional[str] = Form(None),
    credentials_json: Optional[str] = Form(None)
):
    if file_id not in SCHEDULE_CACHE:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan atau sesi telah kadaluarsa.")

    item = SCHEDULE_CACHE[file_id]
    target_url = master_url or item.get("master_url")
    if not target_url:
        raise HTTPException(status_code=400, detail="URL Master Google Sheet tidak ditemukan.")

    try:
        res = write_back_to_google_sheet(
            sheet_url_or_id=target_url,
            assignments=item["assignments"],
            credentials_source=credentials_json
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/schedule/download/{file_id}")
async def download_schedule(file_id: str):
    if file_id not in SCHEDULE_CACHE:
        raise HTTPException(status_code=404, detail="File jadwal tidak ditemukan atau telah kadaluarsa.")

    content = SCHEDULE_CACHE[file_id]["bytes"]
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="master_jadwal_terjadwal.xlsx"'}
    )

def start_server(port: int = 8000, open_browser: bool = True):
    if open_browser:
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    start_server()
