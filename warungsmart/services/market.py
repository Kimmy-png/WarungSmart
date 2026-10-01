"""AI Market Insight: hanya data agregat + anonim, dengan ambang k-anonimitas."""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from warungsmart import config

_REKO = {"Naik": "Tambah stok bertahap", "Turun": "Kurangi pembelian, cek harga",
         "Stabil": "Pertahankan", "Fluktuatif": "Pantau permintaan"}


def market_trends(all_daily: pd.DataFrame, ref: date) -> tuple[pd.DataFrame, int]:
    """Return (tabel tren, jumlah kategori yang disembunyikan karena sampel < k)."""
    k = config.K_ANON_MIN_WARUNG
    w28 = all_daily[(all_daily["tanggal"] > pd.Timestamp(ref - timedelta(days=28)))
                    & (all_daily["tanggal"] <= pd.Timestamp(ref))]
    rows, hidden = [], 0
    for kat, g in w28.groupby("kategori"):
        n = g["warung_id"].nunique()
        if n < k:
            hidden += 1
            continue
        cutoff = pd.Timestamp(ref - timedelta(days=14))
        cur, prv = g[g["tanggal"] > cutoff]["qty"].sum(), g[g["tanggal"] <= cutoff]["qty"].sum()
        chg = (cur - prv) / prv * 100 if prv > 0 else 0.0
        weekly = g.set_index("tanggal")["qty"].resample("W").sum().iloc[1:-1] \
            if g["tanggal"].nunique() > 14 else pd.Series(dtype=float)
        cv = float(weekly.std() / weekly.mean()) if len(weekly) > 1 and weekly.mean() > 0 else 0.0
        if chg >= config.TREND_UP_PCT:
            tren = "Naik"
        elif chg <= config.TREND_DOWN_PCT:
            tren = "Turun"
        else:
            tren = "Fluktuatif" if cv > config.FLUCTUATION_CV else "Stabil"
        rows.append({"Kategori": kat, "Tren": tren, "Perubahan": chg,
                     "Rekomendasi": _REKO[tren], "Sampel (warung)": n})
    df = pd.DataFrame(rows, columns=["Kategori", "Tren", "Perubahan", "Rekomendasi", "Sampel (warung)"])
    return df.sort_values("Perubahan", ascending=False).reset_index(drop=True), hidden
