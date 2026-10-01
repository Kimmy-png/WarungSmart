from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AppContext:
    warung_id: int
    warung_name: str
    today: date
    ref_date: date   # hari terakhir yang tercatat untuk warung terpilih
