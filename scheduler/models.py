from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple, Dict, Any

@dataclass
class Dosen:
    id: int
    name: str
    code: str

@dataclass
class Student:
    id: int
    name: str
    nim: str
    bidang: str
    pembimbing_id: int
    penguji1_id: int
    penguji2_preset_id: Optional[int] = None
    status: str = "aman"

@dataclass
class SessionSlot:
    day_idx: int
    day_name: str
    date_str: str
    session_num: int
    time_range: str
    slot_rows: List[int] = field(default_factory=list)

@dataclass
class ScheduleAssignment:
    student_id: int
    student_name: str
    session_idx: int
    day_name: str
    date_str: str
    session_num: int
    time_range: str
    row_num: int
    urut: int
    pembimbing_id: int
    pembimbing_name: str
    penguji1_id: int
    penguji1_name: str
    penguji2_id: int
    penguji2_name: str

@dataclass
class ParserWarning:
    source: str
    lecturer: Optional[str]
    raw_value: str
    message: str

@dataclass
class ScheduleResult:
    assignments: List[ScheduleAssignment]
    warnings: List[ParserWarning]
    solve_time_ms: float
    total_eligible: int
    scheduled_count: int
