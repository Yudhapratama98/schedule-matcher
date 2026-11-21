from io import BytesIO
from typing import List, Dict, Any
from collections import defaultdict
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

from scheduler.crud import get_active_schedule, list_lecturers, get_settings

def export_db_schedule_to_excel() -> bytes:
    wb = openpyxl.Workbook()
    ws_jadwal = wb.active
    ws_jadwal.title = "Jadwal Ujian"

    settings = get_settings()
    institution_name = settings.get("institution_name", "Program Studi Perencanaan Wilayah dan Kota - ITK")
    raw_rooms = settings.get("room_names", "")
    room_names = [r.strip() for r in raw_rooms.split(",") if r.strip()]

    def format_room(room_num: int) -> str:
        idx = room_num - 1
        if 0 <= idx < len(room_names):
            return room_names[idx]
        return f"Ruang {room_num}"

    title_font = Font(name="Arial", size=12, bold=True, color="0F172A")
    header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="0F766E", end_color="0F766E", fill_type="solid")
    border_thin = Border(
        left=Side(style='thin', color='E2E8F0'),
        right=Side(style='thin', color='E2E8F0'),
        top=Side(style='thin', color='E2E8F0'),
        bottom=Side(style='thin', color='E2E8F0')
    )

    ws_jadwal.cell(row=1, column=1, value=f"Jadwal Ujian Sidang Skripsi — {institution_name}").font = title_font

    headers = [
        "Hari", "Tanggal", "Sesi", "Waktu", "Ruang",
        "Mahasiswa", "NIM", "Bidang", "Pembimbing", "Penguji 1", "Penguji 2", "Status Kunci"
    ]

    for col_idx, h in enumerate(headers, 1):
        cell = ws_jadwal.cell(row=3, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    schedule = get_active_schedule()

    for r_idx, a in enumerate(schedule, 4):
        row_vals = [
            a["day_label"],
            a["date_iso"],
            f"Sesi {a['session_num']}",
            a["time_range"],
            format_room(a["room_num"]),
            a["student_name"],
            a["nim"],
            a["bidang"],
            f"{a['pembimbing_name']} ({a['pembimbing_code']})",
            f"{a['penguji1_name']} ({a['penguji1_code']})",
            f"{a['penguji2_name']} ({a['penguji2_code']})",
            "Terkunci" if a.get("is_locked") else "Otomatis"
        ]
        for c_idx, val in enumerate(row_vals, 1):
            cell = ws_jadwal.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Arial", size=10)
            cell.border = border_thin
            if c_idx in (1, 2, 3, 4, 5, 7, 8, 12):
                cell.alignment = Alignment(horizontal="center", vertical="center")

    # Sheet 2: Beban Dosen
    ws_dosen = wb.create_sheet(title="Beban Dosen")
    ws_dosen.cell(row=1, column=1, value=f"Rekapitulasi Beban Penguji — {institution_name}").font = title_font

    dosen_headers = ["Kode", "Nama Dosen", "P1/P2 (Pembimbing & Penguji 1)", "P3 (Penguji 2)", "Total Sidang"]
    for col_idx, h in enumerate(dosen_headers, 1):
        cell = ws_dosen.cell(row=3, column=col_idx, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    lecturers = list_lecturers()
    p1_p2_counts = defaultdict(int)
    p3_counts = defaultdict(int)

    for a in schedule:
        p1_p2_counts[a["pembimbing_id"]] += 1
        p1_p2_counts[a["penguji1_id"]] += 1
        p3_counts[a["penguji2_id"]] += 1

    for r_idx, l in enumerate(lecturers, 4):
        p1_2 = p1_p2_counts[l["id"]]
        p3 = p3_counts[l["id"]]
        total = p1_2 + p3
        row_vals = [l["code"], l["name"], p1_2, p3, total]
        for c_idx, val in enumerate(row_vals, 1):
            cell = ws_dosen.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Arial", size=10)
            cell.border = border_thin
            if c_idx in (1, 3, 4, 5):
                cell.alignment = Alignment(horizontal="center", vertical="center")

    for ws in [ws_jadwal, ws_dosen]:
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col if cell.row >= 3)
            col_letter = openpyxl.utils.get_column_letter(col[0].column)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
