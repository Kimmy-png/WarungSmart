from __future__ import annotations

from datetime import date

HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]
BULAN = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
         "Agustus", "September", "Oktober", "November", "Desember"]


def rupiah(x: float) -> str:
    return "Rp" + f"{x:,.0f}".replace(",", ".")


def tanggal_id(d: date) -> str:
    return f"{HARI[d.weekday()]}, {d.day} {BULAN[d.month]} {d.year}"
