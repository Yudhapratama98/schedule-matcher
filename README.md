# Sistem Penjadwalan Sidang Skripsi (Schedule Matcher)

Aplikasi penjadwalan mandiri (*standalone production-grade system*) untuk pengelolaan sidang tugas akhir / skripsi mahasiswa. Menggunakan basis data **SQLite** lokal, solver **Google OR-Tools CP-SAT**, pendeteksi bentrok langsung (*live conflict validator*), dan antarmuka web modern (*Laws of UX*).

Tidak memerlukan Google Sheets maupun koneksi internet saat dijalankan.

---

## Fitur Utama

1. **Basis Data SQLite Lokal (`schedule.db`)**:
   - Seluruh data dosen, mahasiswa (*pengajuan sidang*), ketersediaan, dan jadwal tersimpan permanen di komputer lokal.
   - Otomatis diisi (*seeded*) sekali dari berkas data awal (`master.xlsx` & `berhalangan.xlsx`).
2. **Kalkulasi Otomatis Bebas Bentrok (< 2 Detik)**:
   - Dosen tidak pernah dijadwalkan ganda pada hari & sesi yang sama (baik sebagai Pembimbing, Penguji 1, maupun Penguji 2).
   - Menjamin Penguji 2 berbeda dari Pembimbing dan Penguji 1.
   - Menghormati batasan ketersediaan dosen dan kapasitas ruang paralel (default: 5 ruangan).
   - Menyeimbangkan beban Penguji 2 secara adil antar dosen.
3. **Penyuntingan Manual & Deteksi Bentrok Live**:
   - Pengguna dapat menggeser slot hari, sesi, ruangan, maupun mengganti Penguji 2 secara manual.
   - Terdapat tombol **Kunci Slot (Lock)** agar jadwal yang sudah disepakati tidak berubah saat kalkulasi otomatis dijalankan kembali.
   - Deteksi bentrok seketika: sistem langsung menandai warna merah jika terjadi tabrakan jadwal (*double booking* dosen, ruangan dipakai ganda, atau dosen berhalangan).
4. **Matriks Ketersediaan Dosen Interaktif**:
   - Dosen × Tanggal × Sesi 1–4 dapat diubah status ketersediaannya hanya dengan **1 klik** tanpa mengetik manual.
5. **Ekspor Excel Terformat (.xlsx)**:
   - Sekali klik **Unduh .xlsx** menghasilkan laporan terformat lengkap dengan tab `Jadwal Ujian` dan tab `Beban Dosen`.

---

## Cara Menjalankan

### 1. Menjalankan Server Lokal (macOS / Linux / Windows)
```bash
# Aktifkan virtual environment
source .venv/bin/activate  # atau .venv\Scripts\activate di Windows

# Jalankan aplikasi
python app.py
```
Aplikasi akan otomatis membuka peramban di `http://127.0.0.1:8000`.

### 2. Menjalankan Tes Otomatis
```bash
pytest -v
```

### 3. Mengemas Menjadi Executable Windows (.exe)
```cmd
build_exe.bat
```
Atau melalui GitHub Actions (`.github/workflows/build-exe.yml`). File `.exe` siap pakai akan berada di `dist/schedule-matcher.exe`.
