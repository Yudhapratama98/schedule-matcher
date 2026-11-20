import pytest
from scheduler.models import Student, Dosen, SessionSlot
from scheduler.solver import solve_schedule

@pytest.fixture
def sample_dosen():
    return [
        Dosen(id=1, name="Dosen 1", code="D1"),
        Dosen(id=2, name="Dosen 2", code="D2"),
        Dosen(id=3, name="Dosen 3", code="D3"),
        Dosen(id=4, name="Dosen 4", code="D4"),
    ]

@pytest.fixture
def sample_sessions():
    return [
        SessionSlot(day_idx=0, day_name="Senin", date_str="2026-06-01", session_num=1, time_range="08.00-09.30", slot_rows=[6, 7]),
        SessionSlot(day_idx=0, day_name="Senin", date_str="2026-06-01", session_num=2, time_range="10.00-11.30", slot_rows=[8, 9]),
    ]

def test_solver_basic(sample_dosen, sample_sessions):
    students = [
        Student(id=1, name="Mhs A", nim="001", bidang="A", pembimbing_id=1, penguji1_id=2),
        Student(id=2, name="Mhs B", nim="002", bidang="A", pembimbing_id=1, penguji1_id=3),
    ]

    # Both students have Pembimbing=Dosen 1, so they cannot be in the same session!
    result = solve_schedule(
        students=students,
        dosen_list=sample_dosen,
        sessions=sample_sessions,
        blocked_slots=set(),
        auto_assign_p2=True,
        max_rooms_per_slot=2
    )

    assert result.scheduled_count == 2
    # Verify they got assigned to different sessions because Dosen 1 cannot be in 2 defenses at once
    sess_ids = [a.session_idx for a in result.assignments]
    assert sess_ids[0] != sess_ids[1]

    # Verify Penguji 2 distinctness
    for a in result.assignments:
        assert a.penguji2_id != a.pembimbing_id
        assert a.penguji2_id != a.penguji1_id

def test_solver_infeasible_detected(sample_dosen, sample_sessions):
    students = [
        Student(id=1, name="Mhs A", nim="001", bidang="A", pembimbing_id=1, penguji1_id=2),
    ]
    # Block Dosen 1 in all sessions
    blocked = {
        (1, 0, 1),
        (1, 0, 2)
    }
    with pytest.raises(ValueError) as exc:
        solve_schedule(
            students=students,
            dosen_list=sample_dosen,
            sessions=sample_sessions,
            blocked_slots=blocked
        )
    assert "tidak memiliki satupun sesi kosong" in str(exc.value)
