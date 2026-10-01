from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from warungsmart import config


def stock_table(products: pd.DataFrame, daily: pd.DataFrame, ref: date) -> pd.DataFrame:
    w = config.SALES_WINDOW_DAYS
    recent = daily[(daily["tanggal"] > pd.Timestamp(ref - timedelta(days=w)))
                   & (daily["tanggal"] <= pd.Timestamp(ref))]
    avg = recent.groupby("produk_id")["qty"].sum() / w
    df = products[["id", "nama", "kategori", "stok", "stok_min"]].copy()
    df["rata_harian"] = df["id"].map(avg).fillna(0.0)
    df["sisa_hari"] = np.where(df["rata_harian"] > 0, df["stok"] / df["rata_harian"].replace(0, np.nan), np.inf)

    def status(r) -> str:
        if r.stok <= r.stok_min or r.sisa_hari <= config.CRITICAL_DAYS:
            return "Kritis"
        return "Menipis" if r.sisa_hari <= config.LOW_DAYS else "Aman"

    df["status"] = df.apply(status, axis=1)
    need = df["rata_harian"] * config.TARGET_COVER_DAYS - df["stok"]
    df["restock"] = np.where(df["status"] != "Aman", need.clip(lower=0).apply(math.ceil), 0).astype(int)
    order = {"Kritis": 0, "Menipis": 1, "Aman": 2}
    return df.sort_values(by=["status", "sisa_hari"], key=lambda s: s.map(order) if s.name == "status" else s) \
             .reset_index(drop=True)
