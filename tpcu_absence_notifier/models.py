from dataclasses import dataclass


@dataclass(frozen=True)
class AbsenceRecord:
    item: str
    date: str
    period: str
    absence_type: str
