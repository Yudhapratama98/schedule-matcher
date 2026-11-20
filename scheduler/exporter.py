from io import BytesIO
from typing import Union, List
import openpyxl

from scheduler.models import ScheduleAssignment

def export_schedule_to_excel(
    master_template: Union[str, bytes],
    assignments: List[ScheduleAssignment]
) -> bytes:
    wb = openpyxl.load_workbook(
        BytesIO(master_template) if isinstance(master_template, bytes) else master_template,
        data_only=False
    )
    if 'Jadwal' not in wb.sheetnames:
        raise ValueError("Sheet 'Jadwal' tidak ditemukan di template master.")

    ws = wb['Jadwal']

    # 1. Clear previous Mhs (col 16 / P) and Dosen (col 17 / Q) values from row 6 onwards
    for r in range(6, ws.max_row + 1):
        # Clear columns 16 and 17
        ws.cell(r, 16).value = None
        ws.cell(r, 17).value = None

    # 2. Write new assignments into columns P and Q
    for a in assignments:
        ws.cell(a.row_num, 16).value = int(a.student_id)
        ws.cell(a.row_num, 17).value = int(a.penguji2_id)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
