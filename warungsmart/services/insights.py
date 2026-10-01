"""AI Personal Insight (rule + statistik ringan, transparan & bisa diaudit)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd

from warungsmart import config
from warungsmart.services import analytics, inventory


@dataclass
class Insight:
    title: str
    body: str
    tone: str = "info"   # info | warn | good


def _juta(x: float) -> str:
    return f"{x / 1e6:.1f}".replace(".", ",")


def forecast_revenue(daily: pd.DataFrame, ref: date) -> dict | None:
    hist = analytics.daily_revenue(daily, ref, config.FORECAST_HISTORY_DAYS)
    if hist.sum() == 0:
        return None
    n, h = len(hist), config.FORECAST_HORIZON_DAYS
    x = np.arange(n)
    slope, icpt = np.polyfit(x, hist.values, 1)
    fit = icpt + slope * x
    band = float(np.std(hist.values - fit)) * math.sqrt(h)
    future = np.clip(icpt + slope * np.arange(n, n + h), 0, None)
    mid = float(future.sum())
    idx = pd.date_range(ref + timedelta(days=1), periods=h)
    return {"mid": mid, "low": max(0.0, mid - band), "high": mid + band,
            "history": hist, "future": pd.Series(future, index=idx)}


def category_growth(daily: pd.DataFrame, ref: date, days: int = 7) -> pd.Series:
    cur = analytics._between(daily, ref - timedelta(days=days - 1), ref).groupby("kategori")["qty"].sum()
    prv = analytics._between(daily, ref - timedelta(days=2 * days - 1), ref - timedelta(days=days)) \
        .groupby("kategori")["qty"].sum()
    g = ((cur - prv) / prv.replace(0, np.nan) * 100).dropna()
    return g.sort_values(ascending=False)


def margin_table(daily: pd.DataFrame, ref: date, days: int = 30) -> pd.DataFrame:
    w = analytics._between(daily, ref - timedelta(days=days - 1), ref)
    g = w.groupby("produk")[["total", "laba", "qty"]].sum()
    g["margin"] = g["laba"] / g["total"]
    return g


def price_recommendation(daily: pd.DataFrame, products: pd.DataFrame, ref: date) -> dict | None:
    top = analytics.top_products(daily, ref, n=5)["produk"]
    p = products[products["nama"].isin(top)].copy()
    p["margin"] = (p["harga_jual"] - p["harga_beli"]) / p["harga_jual"]
    p = p[p["margin"] < config.TARGET_MARGIN].sort_values("margin")
    if p.empty:
        return None
    r = p.iloc[0]
    step = config.PRICE_ROUNDING
    saran = math.ceil(r.harga_beli / (1 - config.TARGET_MARGIN) / step) * step
    return {"produk": r.nama, "margin": float(r.margin), "harga_saat_ini": float(r.harga_jual),
            "harga_saran": float(saran)}


def personal_insights(daily: pd.DataFrame, products: pd.DataFrame, ref: date) -> list[Insight]:
    out: list[Insight] = []

    st = inventory.stock_table(products, daily, ref)
    risk = st[st["status"] != "Aman"].head(3)
    if risk.empty:
        out.append(Insight("Stok aman", "Semua produk punya stok cukup untuk lebih dari 7 hari.", "good"))
    else:
        names = ", ".join(risk["nama"])
        d = risk["sisa_hari"].replace(np.inf, np.nan).dropna()
        span = f"{d.min():.0f}–{d.max():.0f}" if len(d) and round(d.min()) != round(d.max()) else f"{d.min():.0f}"
        out.append(Insight("Restock disarankan", f"{names} berpotensi habis dalam {span} hari.", "warn"))

    g = category_growth(daily, ref)
    if len(g) and g.iloc[0] > 0:
        out.append(Insight("Tren naik", f"Penjualan {g.index[0].lower()} meningkat {g.iloc[0]:.0f}% "
                                        "dibanding 7 hari sebelumnya.", "good"))
    elif len(g):
        out.append(Insight("Tren stabil", "Tidak ada kategori dengan kenaikan penjualan berarti minggu ini."))

    m = margin_table(daily, ref)
    if len(m):
        avg = m["laba"].sum() / m["total"].sum()
        low = m[(m["margin"] < avg) & (m["total"] >= m["total"].median())]
        if len(low):
            out.append(Insight("Peringatan margin",
                               f"{len(low)} produk beromzet tinggi tetapi margin di bawah rata-rata "
                               f"({avg:.0%}): {', '.join(low.index[:3])}. Periksa harga beli.", "warn"))

    fc = forecast_revenue(daily, ref)
    if fc:
        out.append(Insight("Prediksi omzet",
                           f"Jika pola saat ini berlanjut, omzet 30 hari ke depan berada di kisaran "
                           f"Rp{_juta(fc['low'])}–{_juta(fc['high'])} juta."))
    return out
