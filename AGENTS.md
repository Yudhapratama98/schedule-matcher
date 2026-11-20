# AGENTS.md

## Project Goal
Build and maintain `schedule-matcher`: automate thesis defense scheduling (*jadwal ujian skripsi*) by assigning eligible students to time slots/rooms and balancing `Penguji 2` without lecturer conflicts (*bentrok*) using Google OR-Tools CP-SAT and a clean web UI.

## Developer Commands
- Run application locally: `.venv/bin/python app.py` (auto-opens `http://127.0.0.1:8000`).
- Run all tests: `.venv/bin/pytest -v` (runs parser, solver, and full integration tests on real test data).
- Build Windows `.exe`: `pyinstaller schedule-matcher.spec` (or trigger GitHub Actions on `windows-latest`).

## Architecture & Conventions
- `scheduler/parser.py`: Reads `master.xlsx` (`Mahasiswa`, `Dosen`, `Jadwal`) and `berhalangan.xlsx`. Normalizes lecturer names using token sorting/subset matching. Parses free-text availability and cuts off old template rows when dates jump backwards.
- `scheduler/solver.py`: Formulates OR-Tools CP-SAT model. Enforces 100% hard constraints (no double-booking, distinct examiners, room capacity, blocked slots) and soft objectives (balanced Penguji 2 workload + earlier session preference). Solves in ~1-2 seconds.
- `scheduler/exporter.py`: Copies original workbook, clears previous values in columns P & Q (`cell.value = None`), and writes assigned `Mhs` and `Dosen` IDs to preserve original formatting and Excel formulas.
- `scheduler/gsheets.py`: Handles Google Sheets fetching directly via export URL (zero auth for public links) and writing back to live sheets using `gspread` (Service Account / credentials).
- `app.py`: FastAPI server serving `static/index.html` and handling `/api/schedule`, `/api/schedule/sync-google-sheet`, and `/api/schedule/download/{file_id}`.
- `static/index.html`: Clean, utilitarian UI compliant with Laws of UX (tabular nums, clear hierarchy, no generic AI styling). Automatically pre-fills Google Sheet links from `.env`.

## Gotchas & Quirks
- **openpyxl**: Calling `ws.cell(r, c, value=None)` does NOT clear the cell value (default argument is ignored). Always use `ws.cell(r, c).value = None`.
- **Packaging**: `ortools` bundles native C++ binaries; always use `schedule-matcher.spec` which uses `collect_all('ortools')` and bundles the `static/` directory.
