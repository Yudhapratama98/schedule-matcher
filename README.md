# Penjadwalan Ujian Skripsi (Schedule Matcher)

Aplikasi penjadwalan otomatis ujian skripsi / tugas akhir mahasiswa untuk Program Studi, menyelesaikan kendala bentrok jadwal dosen penguji/pembimbing dan menyeimbangkan beban penguji secara otomatis dengan Google OR-Tools CP-SAT.

---

## Fitur Utama

1. **Koneksi Langsung Google Sheets & Unggah Berkas**:
   - Membaca link Google Sheets langsung (otomatis terisi dari `.env`).
   - Dapat menulis hasil jadwal langsung kembali ke tab `Jadwal` di Google Sheets secara live, atau diunduh sebagai file `.xlsx`.
2. **Bebas Bentrok 100% (Hard Constraints)**:
   - Dosen tidak pernah dijadwalkan ganda pada hari & sesi yang sama, baik sebagai Pembimbing, Penguji 1, maupun Penguji 2.
   - Penguji 2 dijamin berbeda dari Pembimbing dan Penguji 1 mahasiswa terkait.
   - Menghormati batasan berhalangan dosen dari sheet berhalangan (misal: "Sesi 1, 3", "Latsar", "Survei Riset").
   - Kapasitas ruangan per sesi dibatasi sesuai ketersediaan ruangan (default: 5 ruangan paralel).
3. **Keseimbangan Beban Penguji (Soft Constraints)**:
   - Meminimalkan selisih beban Penguji 2 antar dosen secara merata (pada 46 mahasiswa & 16 dosen, selisih maksimal hanya 1 mahasiswa).
   - Memprioritaskan sesi-sesi awal agar jadwal sidang tidak molor berminggu-minggu.
4. **Kompatibel Penuh dengan Template Excel & Google Sheets**:
   - Menulis langsung kode mahasiswa (`Mhs` / kolom P) dan kode penguji (`Dosen` / kolom Q) ke sheet `Jadwal`.
   - Seluruh rumus `VLOOKUP`, rumus nama, bidang minat, dan kontrol formula bawaan Excel tetap aktif.
5. **Antarmuka Bersih & Utilitarian (Laws of UX)**:
   - Dirancang sesuai prinsip *Jakob's Law*, *Hick's Law*, *Miller's Law*, dan *Postel's Law*.
   - Filter pencarian cepat, pratinjau kartu sesi, tabel rekapitulasi beban dosen, serta banner peringatan jika ada teks ketersediaan yang ambigu.

---

## Cara Menjalankan

### 1. Menjalankan Langsung via Python (macOS / Linux / Windows)
```bash
# Aktifkan virtual environment
source .venv/bin/activate  # atau .venv\Scripts\activate di Windows

# Jalankan server
python app.py
```
Aplikasi akan otomatis membuka peramban di `http://127.0.0.1:8000`.

### 2. Menjalankan Pengujian (Tests)
```bash
pytest -v
```

### 3. Mengemas Menjadi Executable Windows (.exe)
- **Otomatis via GitHub Actions**:
  Push kode ke GitHub, dan workflow `.github/workflows/build-exe.yml` akan otomatis menghasilkan file `schedule-matcher.exe` siap unduh.
- **Lokal di Windows**:
  Jalankan `build_exe.bat` atau perintah:
  ```cmd
  pip install -r requirements.txt pyinstaller
  pyinstaller schedule-matcher.spec
  ```
  File `.exe` mandiri akan tersedia di folder `dist/schedule-matcher.exe`.
