# AGENTS.md

## Project Goal
Build and maintain `schedule-matcher`: a production-grade thesis defense scheduling application (*sistem penjadwalan ujian skripsi*) with SQLite database, interactive availability matrix, manual conflict editor with live validation, Google OR-Tools CP-SAT solver, and world-class UI.

## Developer Commands
- Run application locally: `.venv/bin/python app.py` (auto-opens `http://127.0.0.1:8000`).
- Run all tests: `.venv/bin/pytest -v` (runs SQLite seeding, CRUD, CP-SAT solver, live conflict validator, and REST API tests).
- Build Windows `.exe`: `pyinstaller schedule-matcher.spec` (or trigger GitHub Actions on `windows-latest`).

## Architecture & Conventions
- `scheduler/db.py`: SQLite setup with WAL mode and foreign keys enabled. Manages `students`, `lecturers`, `exam_days`, `sessions`, `lecturer_blocks`, `schedule_assignments`, and `app_settings`.
- `scheduler/seed.py`: One-time seed from Excel files (`master.xlsx` and `berhalangan.xlsx`) to populate the database on initial start.
- `scheduler/crud.py`: Full CRUD for students, lecturers, exam days, interactive blocks, settings, and live conflict validator (`validate_conflicts()`).
- `scheduler/db_solver.py`: Formulates OR-Tools CP-SAT model directly against SQLite. Supports slot locking (`is_locked = 1`), room assignment, and workload balancing in < 2s.
- `scheduler/db_exporter.py`: Generates styled multi-sheet `.xlsx` (`Jadwal Ujian` and `Beban Dosen`) directly from database state.
- `app.py`: FastAPI server serving `static/index.html` and REST endpoints.
- `static/index.html`: Responsive, utilitarian UI compliant with Laws of UX (4 rail views: `Jadwal & Konflik`, `Pengajuan Mahasiswa`, `Dosen & Berhalangan`, and `Pengaturan Sesi`).

## Gotchas & Quirks
- **Database Path**: Defaults to `schedule.db` in working directory. Auto-seeded once if empty and seed files exist.
- **openpyxl**: Calling `ws.cell(r, c, value=None)` does NOT clear the cell value. Always use `ws.cell(r, c).value = None`.
- **Packaging**: `schedule-matcher.spec` bundles `static/` directory and uses `collect_all('ortools')`.
