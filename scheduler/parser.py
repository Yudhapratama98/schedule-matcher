import re
import datetime
from io import BytesIO
from typing import List, Tuple, Set, Dict, Optional, Union, Any
import openpyxl

from scheduler.models import Dosen, Student, SessionSlot, ParserWarning

def normalize_text(s: str) -> str:
    s = re.sub(r'\(.*?\)', '', s)
    s = re.sub(r'[^a-zA-Z\s]', '', s).lower()
    tokens = sorted(s.split())
    return ' '.join(tokens)

def to_date_obj(v: Any) -> Optional[datetime.date]:
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, (int, float)):
        try:
            return (datetime.datetime(1899, 12, 30) + datetime.timedelta(days=float(v))).date()
        except Exception:
            return None
    return None

def parse_blocked_sessions_text(text: str) -> Tuple[Set[int], Optional[str]]:
    raw = str(text).strip()
    tl = raw.lower()
    full_day_keywords = ['latsar', 'survei', 'riset', 'dinas', 'cuti', 'full', 'semua', 'sehari']
    if any(k in tl for k in full_day_keywords):
        return {1, 2, 3, 4}, None

    m_range = re.search(r'sesi\s*([1-4])\s*[-–—]\s*([1-4])', tl)
    if m_range:
        s_start, s_end = int(m_range.group(1)), int(m_range.group(2))
        return set(range(min(s_start, s_end), max(s_start, s_end) + 1)), None

    digits = [int(d) for d in re.findall(r'\b([1-4])\b', tl)]
    if digits:
        return set(digits), None

    return set(), f'Format jadwal tidak dikenali: "{raw}" (diabaikan, mohon diverifikasi manual)'

def match_dosen(raw_name: Optional[str], dosen_map: Dict[str, Dosen]) -> Optional[Dosen]:
    if not raw_name:
        return None
    n = normalize_text(raw_name)
    if not n:
        return None
    if n in dosen_map:
        return dosen_map[n]

    raw_tokens = set(n.split())
    for k, d in dosen_map.items():
        k_tokens = set(k.split())
        if raw_tokens.issubset(k_tokens) or k_tokens.issubset(raw_tokens):
            return d
    return None

def load_master_and_berhalangan(
    master_file: Union[str, bytes],
    berhalangan_file: Union[str, bytes]
) -> Tuple[List[Student], List[Dosen], List[SessionSlot], Set[Tuple[int, int, int]], List[ParserWarning]]:
    warnings: List[ParserWarning] = []

    # 1. Load Master Workbook
    master_wb = openpyxl.load_workbook(
        BytesIO(master_file) if isinstance(master_file, bytes) else master_file,
        data_only=True
    )
    if 'Dosen' not in master_wb.sheetnames:
        raise ValueError("Sheet 'Dosen' tidak ditemukan di master.xlsx")
    if 'Mahasiswa' not in master_wb.sheetnames:
        raise ValueError("Sheet 'Mahasiswa' tidak ditemukan di master.xlsx")
    if 'Jadwal' not in master_wb.sheetnames:
        raise ValueError("Sheet 'Jadwal' tidak ditemukan di master.xlsx")

    # 2. Parse Dosen
    ws_dosen = master_wb['Dosen']
    dosen_list: List[Dosen] = []
    dosen_map: Dict[str, Dosen] = {}
    dosen_by_id: Dict[int, Dosen] = {}

    for r in range(2, ws_dosen.max_row + 1):
        k = ws_dosen.cell(r, 1).value
        n = ws_dosen.cell(r, 2).value
        if k is not None and n is not None:
            try:
                d_id = int(k)
            except ValueError:
                continue
            name_str = str(n).strip()
            m_code = re.search(r'\((.*?)\)', name_str)
            code = m_code.group(1).strip() if m_code else f"D{d_id}"
            d_obj = Dosen(id=d_id, name=name_str, code=code)
            dosen_list.append(d_obj)
            dosen_map[normalize_text(name_str)] = d_obj
            dosen_by_id[d_id] = d_obj

    if not dosen_list:
        raise ValueError("Tidak ada data dosen yang valid di sheet 'Dosen'")

    # 3. Parse Mahasiswa
    ws_mhs = master_wb['Mahasiswa']
    students: List[Student] = []

    for r in range(2, ws_mhs.max_row + 1):
        k = ws_mhs.cell(r, 1).value
        nama = ws_mhs.cell(r, 2).value
        nim = ws_mhs.cell(r, 3).value
        bidang = ws_mhs.cell(r, 4).value
        pemb = ws_mhs.cell(r, 5).value
        peng1 = ws_mhs.cell(r, 6).value
        peng2 = ws_mhs.cell(r, 8).value
        status = ws_mhs.cell(r, 10).value

        if k is None or nama is None:
            continue

        try:
            m_id = int(k)
        except ValueError:
            continue

        status_str = str(status).strip() if status is not None else ""
        if status_str.lower() != "aman":
            continue

        pemb_obj = match_dosen(str(pemb) if pemb else None, dosen_map)
        peng1_obj = match_dosen(str(peng1) if peng1 else None, dosen_map)
        peng2_obj = match_dosen(str(peng2) if peng2 else None, dosen_map)

        if not pemb_obj:
            raise ValueError(f"Mahasiswa '{nama}' (baris {r}): Pembimbing '{pemb}' tidak cocok dengan daftar Dosen.")
        if not peng1_obj:
            raise ValueError(f"Mahasiswa '{nama}' (baris {r}): Penguji 1 '{peng1}' tidak cocok dengan daftar Dosen.")

        students.append(Student(
            id=m_id,
            name=str(nama).strip(),
            nim=str(nim).strip() if nim is not None else "",
            bidang=str(bidang).strip() if bidang is not None else "",
            pembimbing_id=pemb_obj.id,
            penguji1_id=peng1_obj.id,
            penguji2_preset_id=peng2_obj.id if peng2_obj else None,
            status=status_str
        ))

    # 4. Parse Jadwal layout
    ws_jadwal = master_wb['Jadwal']
    sessions: List[SessionSlot] = []

    cur_day_name = "Hari"
    cur_date_str = ""
    day_counter = -1
    last_day_seen = None

    r = 6
    while r <= ws_jadwal.max_row:
        u_val = ws_jadwal.cell(r, 3).value
        if u_val is None:
            break

        h1 = ws_jadwal.cell(r, 1).value
        h2 = ws_jadwal.cell(r + 1, 1).value
        w1 = ws_jadwal.cell(r, 2).value
        w2 = ws_jadwal.cell(r + 1, 2).value

        dt_candidate = to_date_obj(h1) or to_date_obj(h2)
        day_str_candidate = str(h1).strip() if h1 and not to_date_obj(h1) else (str(h2).strip() if h2 and not to_date_obj(h2) else None)

        if day_str_candidate or dt_candidate:
            cur_day_name = day_str_candidate or cur_day_name
            if dt_candidate:
                new_date_str = dt_candidate.strftime('%Y-%m-%d')
                # If date jumps backward to a past date (leftover template rows from old semester), stop
                if cur_date_str and new_date_str < cur_date_str:
                    break
                cur_date_str = new_date_str
            day_identifier = (cur_day_name, cur_date_str)
            if day_identifier != last_day_seen:
                day_counter += 1
                last_day_seen = day_identifier

        time_str = f"{str(w1).strip() if w1 else ''} - {str(w2).strip() if w2 else ''}".strip(" -")
        if not time_str:
            time_str = "Sesi Waktu"

        session_num_in_day = (len([s for s in sessions if s.day_idx == max(0, day_counter)]) % 4) + 1
        slot_rows = [r + offset for offset in range(5) if ws_jadwal.cell(r + offset, 3).value is not None]

        sessions.append(SessionSlot(
            day_idx=max(0, day_counter),
            day_name=cur_day_name,
            date_str=cur_date_str,
            session_num=session_num_in_day,
            time_range=time_str,
            slot_rows=slot_rows
        ))
        r += 5

    # 5. Parse Berhalangan
    berh_wb = openpyxl.load_workbook(
        BytesIO(berhalangan_file) if isinstance(berhalangan_file, bytes) else berhalangan_file,
        data_only=True
    )
    ws_b = berh_wb.active

    # Determine unique days in Jadwal
    unique_j_days = []
    seen_days = set()
    for s in sessions:
        if s.day_idx not in seen_days:
            seen_days.add(s.day_idx)
            unique_j_days.append((s.day_idx, s.day_name, s.date_str))

    # Read columns in Berhalangan (C onwards)
    b_cols: List[Tuple[int, str, Optional[datetime.date]]] = []
    for c in range(3, ws_b.max_column + 1):
        day_label = ws_b.cell(4, c).value
        d_val = ws_b.cell(5, c).value
        d_date = to_date_obj(d_val)
        day_str = str(day_label).strip().upper() if day_label else ""
        if day_str or d_date:
            b_cols.append((c, day_str, d_date))

    # Build mapping from Berhalangan col index -> Jadwal day_idx
    col_to_day_idx: Dict[int, int] = {}

    # Try matching by exact date first
    matched_by_date = False
    date_to_j_day = {j_date: j_idx for j_idx, _, j_date in unique_j_days if j_date}
    for col_idx, _, b_date in b_cols:
        if b_date and b_date.strftime('%Y-%m-%d') in date_to_j_day:
            col_to_day_idx[col_idx] = date_to_j_day[b_date.strftime('%Y-%m-%d')]
            matched_by_date = True

    if not matched_by_date:
        # Match sequentially by day name / index
        # Berhalangan typically has 10 days (2 weeks). Map to available Jadwal days.
        for i, (col_idx, b_day_name, _) in enumerate(b_cols):
            # Find matching day in unique_j_days
            for j_idx, j_day_name, _ in unique_j_days:
                if b_day_name and b_day_name.lower() in j_day_name.lower():
                    # check week matching if multiple
                    if col_idx not in col_to_day_idx:
                        col_to_day_idx[col_idx] = j_idx
                        break
            if col_idx not in col_to_day_idx and i < len(unique_j_days):
                col_to_day_idx[col_idx] = unique_j_days[i][0]

    blocked_tuples: Set[Tuple[int, int, int]] = set() # (dosen_id, day_idx, session_num)

    for r in range(6, ws_b.max_row + 1):
        nama_cell = ws_b.cell(r, 2).value
        if not nama_cell:
            continue
        d_obj = match_dosen(str(nama_cell), dosen_map)
        if not d_obj:
            warnings.append(ParserWarning(
                source="berhalangan.xlsx",
                lecturer=str(nama_cell),
                raw_value=str(nama_cell),
                message=f"Dosen '{nama_cell}' di berhalangan.xlsx tidak cocok dengan data Dosen master."
            ))
            continue

        for col_idx, day_str, _ in b_cols:
            cell_val = ws_b.cell(r, col_idx).value
            if not cell_val:
                continue
            blocked_sess, warn = parse_blocked_sessions_text(str(cell_val))
            if warn:
                warnings.append(ParserWarning(
                    source="berhalangan.xlsx",
                    lecturer=d_obj.name,
                    raw_value=str(cell_val),
                    message=warn
                ))

            if col_idx in col_to_day_idx:
                target_day_idx = col_to_day_idx[col_idx]
                for s_num in blocked_sess:
                    blocked_tuples.add((d_obj.id, target_day_idx, s_num))

    return students, dosen_list, sessions, blocked_tuples, warnings
