from __future__ import annotations

from datetime import date, timedelta

import pandas as pd


def _between(daily: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    return daily[(daily["tanggal"] >= pd.Timestamp(start)) & (daily["tanggal"] <= pd.Timestamp(end))]


def month_kpis(daily: pd.DataFrame, ref: date) -> dict:
    m = _between(daily, ref.replace(day=1), ref)
    return {"omzet": float(m["total"].sum()), "laba": float(m["laba"].sum()),
            "terjual": int(m["qty"].sum())}


def weekly_performance(daily: pd.DataFrame, ref: date, weeks: int = 4) -> pd.DataFrame:
    rows = []
    for i in range(weeks):
        end = ref - timedelta(days=7 * (weeks - 1 - i))
        omzet = float(_between(daily, end - timedelta(days=6), end)["total"].sum())
        rows.append({"minggu": f"Minggu {i + 1}", "omzet": omzet})
    df = pd.DataFrame(rows)
    df["pct"] = (df["omzet"] / df["omzet"].max() * 100).fillna(0) if df["omzet"].max() > 0 else 0
    return df


def top_products(daily: pd.DataFrame, ref: date, n: int = 3, days: int = 30) -> pd.DataFrame:
    w = _between(daily, ref - timedelta(days=days - 1), ref)
    return (w.groupby("produk")["qty"].sum().sort_values(ascending=False)
            .head(n).reset_index())


def daily_revenue(daily: pd.DataFrame, ref: date, days: int = 30) -> pd.Series:
    idx = pd.date_range(end=pd.Timestamp(ref), periods=days)
    s = daily.groupby("tanggal")["total"].sum()
    return s.reindex(idx, fill_value=0.0)
