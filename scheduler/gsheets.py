import re
import os
import json
import urllib.request
from typing import Optional, Union, Dict, Any, List
import gspread
from google.oauth2.service_account import Credentials

from scheduler.models import ScheduleAssignment

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def extract_sheet_id(url_or_id: str) -> str:
    if not url_or_id:
        return ""
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url_or_id)
    if m:
        return m.group(1)
    return url_or_id.strip()

def fetch_google_sheet_as_xlsx(sheet_url_or_id: str, credentials_data: Optional[Union[dict, str]] = None) -> bytes:
    sheet_id = extract_sheet_id(sheet_url_or_id)
    if not sheet_id:
        raise ValueError("URL Google Sheets tidak valid.")

    # 1. Try public export URL first
    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"
    req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read()
            if len(content) > 1000 and b"PK" in content[:4]:
                return content
    except Exception:
        pass

    # 2. If public export fails, attempt authenticated download using service account credentials
    creds = get_credentials(credentials_data)
    if not creds:
        raise ValueError(
            "Gagal mengunduh Google Sheet secara publik. Pastikan link diatur ke 'Siapa saja yang memiliki link dapat melihat' "
            "atau konfigurasikan file Kredensial Google (Service Account)."
        )

    client = gspread.authorize(creds)
    # Open spreadsheet to verify access
    try:
        sh = client.open_by_key(sheet_id)
        # Fetch export using authorized session
        session = client.http_client.session
        auth_resp = session.get(export_url, timeout=30)
        if auth_resp.status_code == 200:
            return auth_resp.content
        raise ValueError(f"Google Drive API mengembalikan status {auth_resp.status_code}")
    except Exception as e:
        raise ValueError(f"Gagal mengakses Google Sheet dengan kredensial: {str(e)}")

def get_credentials(credentials_source: Optional[Union[dict, str]] = None) -> Optional[Credentials]:
    # 1. Directly passed dict
    if isinstance(credentials_source, dict):
        return Credentials.from_service_account_info(credentials_source, scopes=SCOPES)

    # 2. Directly passed json string or filepath
    if isinstance(credentials_source, str) and credentials_source.strip():
        val = credentials_source.strip()
        if os.path.exists(val):
            return Credentials.from_service_account_file(val, scopes=SCOPES)
        if val.startswith("{"):
            try:
                data = json.loads(val)
                return Credentials.from_service_account_info(data, scopes=SCOPES)
            except Exception:
                pass

    # 3. Local file service_account.json
    local_path = os.path.join(os.getcwd(), "service_account.json")
    if os.path.exists(local_path):
        return Credentials.from_service_account_file(local_path, scopes=SCOPES)

    # 4. Environment variable GOOGLE_SERVICE_ACCOUNT_JSON or CREDENTIALS_JSON
    env_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("CREDENTIALS_JSON")
    if env_json:
        if os.path.exists(env_json):
            return Credentials.from_service_account_file(env_json, scopes=SCOPES)
        try:
            data = json.loads(env_json)
            return Credentials.from_service_account_info(data, scopes=SCOPES)
        except Exception:
            pass

    return None

def write_back_to_google_sheet(
    sheet_url_or_id: str,
    assignments: List[ScheduleAssignment],
    credentials_source: Optional[Union[dict, str]] = None
) -> Dict[str, Any]:
    sheet_id = extract_sheet_id(sheet_url_or_id)
    if not sheet_id:
        raise ValueError("URL Google Sheets tidak valid.")

    creds = get_credentials(credentials_source)
    if not creds:
        return {
            "success": False,
            "requires_credentials": True,
            "message": "Kredensial Service Account Google belum dikonfigurasi. Anda dapat mengunggah service_account.json atau menggunakan tombol 'Unduh .xlsx'."
        }

    client = gspread.authorize(creds)
    try:
        sh = client.open_by_key(sheet_id)
    except Exception as e:
        service_email = getattr(creds, "service_account_email", "email service account")
        raise ValueError(
            f"Gagal membuka spreadsheet Google. Pastikan Anda telah membagikan sheet tersebut ke email Service Account: "
            f"{service_email} dengan akses 'Editor'."
        )

    try:
        ws = sh.worksheet("Jadwal")
    except Exception:
        raise ValueError("Worksheet 'Jadwal' tidak ditemukan pada Google Sheet yang dituju.")

    # Prepare batch update:
    # 1. Clear existing P and Q columns for rows 6..200
    clear_updates = []
    for r in range(6, 200):
        clear_updates.append({"range": f"P{r}:Q{r}", "values": [["", ""]]})

    # 2. Assign newly scheduled students into P and Q
    write_updates = []
    for a in assignments:
        write_updates.append({
            "range": f"P{a.row_num}:Q{a.row_num}",
            "values": [[int(a.student_id), int(a.penguji2_id)]]
        })

    # Execute batch updates
    ws.batch_update(clear_updates)
    ws.batch_update(write_updates)

    return {
        "success": True,
        "sheet_title": sh.title,
        "worksheet_title": ws.title,
        "updated_rows": len(assignments),
        "message": f"Berhasil menulis {len(assignments)} jadwal mahasiswa langsung ke Google Sheet '{sh.title}'!"
    }
