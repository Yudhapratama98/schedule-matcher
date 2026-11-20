What your friend is trying to solve
She manages thesis defense scheduling (jadwal ujian skripsi) for her department (prodi). Currently, she uses Excel/Google Sheets, which only auto-fills names—it doesn't actually schedule anything. She still has to manually figure out which student goes into which time slot and which lecturer becomes Penguji 2 without causing any double-bookings (bentrok).
With ≤ 10 students, doing this by eye is manageable. With > 20 students, checking every lecturer's conflicts across parallel time slots becomes a huge headache.
How her current spreadsheet works (from her messages + screenshot)
1. Mahasiswa tab (her input list):
- A numbered list of students taking the defense, each already paired with their Pembimbing (Advisor) and Penguji 1 (Examiner 1).
2. Jadwal tab (the screenshot):
- Time blocks (Hari + Waktu): Each time slot (e.g., Rabu 17-Jun 08.00–09.30) has 5 parallel rows (Urut 1–5), meaning up to 5 defenses can run at the same time in different rooms (Ruangan).
- Red box (Mhs | Dosen): These are the two numbers she types in manually for each slot:
- Mhs: The student's number from the Mahasiswa tab. Typing it auto-fills Mahasiswa, Pembimbing, and Penguji 1.
- Dosen: A lecturer's code number for Penguji 2 (Examiner 2).
- Green box (Kode | Nama): The lookup table (codes 1–30) that translates the Dosen number in the red box into the Penguji 2 name (e.g., 4 → Ummu Kultsum Muhammad (UMU)).
3. Other tabs (Dosen, Tidak Maju):
- Likely hold lecturer availability/schedules (Dosen) and students who aren't defending yet (Tidak Maju).
What the automated system needs to do
Instead of her manually guessing Mhs and Dosen numbers and checking for clashes, an automated scheduler would take her inputs and generate a valid Jadwal automatically:
- Inputs:
- Students (with fixed Pembimbing + Penguji 1).
- Lecturers (codes, plus any unavailable time slots).
- Available time slots & room capacity per slot (e.g., 5 parallel slots).
- Rules it must enforce (Hard Constraints):
- No lecturer conflicts (bentrok): A lecturer cannot appear twice in the same Hari + Waktu block—whether as Pembimbing, Penguji 1, or Penguji 2.
- Distinct examiners: Penguji 2 cannot be the same person as that student's Pembimbing or Penguji 1.
- Availability: Respect any blocked times for lecturers (or students).
- Slot capacity: Don't exceed the number of available rooms/parallel slots per time block.
- Nice-to-have goals (Soft Constraints):
- Balance Penguji 2 assignments fairly across lecturers.
- Group a lecturer's sessions into fewer days/blocks so they aren't waiting around all day.
- Output:
- A conflict-free Jadwal (ideally exportable to Excel/CSV so she can drop it straight into her existing template).

All of the mentioned xlsx are in .env