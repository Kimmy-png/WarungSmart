"""Penanganan granularitas waktu di backend.

Semua service membaca data lewat `to_daily()`. Baris per jam (jika ada) dilipat
menjadi harian, sehingga skema DB tidak perlu berubah. Fitur per jam hanya aktif
bila flag menyala DAN data memang memiliki jam.
"""
from __future__ import annotations

import pandas as pd

from warungsmart import config

_KEYS = ["warung_id", "produk_id", "produk", "kategori", "tanggal"]
_VALS = ["qty", "total", "hpp", "laba"]


def to_daily(sales: pd.DataFrame) -> pd.DataFrame:
    keys = [k for k in _KEYS if k in sales.columns]
    if sales.empty:
        return pd.DataFrame(columns=keys + _VALS)
    return sales.groupby(keys, as_index=False)[_VALS].sum()


def hourly_available(sales: pd.DataFrame) -> bool:
    return config.HOURLY_FEATURES_ENABLED and "jam" in sales and sales["jam"].notna().any()


def hourly_profile(sales: pd.DataFrame) -> pd.Series | None:
    """Profil jam sibuk; None bila fitur nonaktif / data tidak punya jam."""
    if not hourly_available(sales):
        return None
    return sales.dropna(subset=["jam"]).groupby("jam")["qty"].sum()
