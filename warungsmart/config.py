"""Konfigurasi terpusat. Semua threshold bisnis ada di sini, bukan di UI."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("WARUNGSMART_DB", ROOT / "data" / "warungsmart.db"))

# --- Granularitas data -------------------------------------------------------
# Pencatatan dilakukan HARIAN. Kolom `transaksi.jam` tetap ada di database
# (nullable) sehingga skema tidak berubah; fitur per jam dimatikan di backend.
HOURLY_FEATURES_ENABLED = False

# --- Persediaan --------------------------------------------------------------
SALES_WINDOW_DAYS = 14      # jendela rata-rata penjualan harian
CRITICAL_DAYS = 3           # sisa stok <= 3 hari  -> Kritis
LOW_DAYS = 7                # sisa stok <= 7 hari  -> Menipis
TARGET_COVER_DAYS = 10      # restock agar cukup untuk 10 hari

# --- Harga & margin ----------------------------------------------------------
TARGET_MARGIN = 0.20        # target margin kotor 20%
PRICE_ROUNDING = 100        # pembulatan harga saran (Rp)

# --- Privasi (AI Market Insight) --------------------------------------------
K_ANON_MIN_WARUNG = 3       # kategori tampil hanya jika >= 3 warung berkontribusi
TREND_UP_PCT = 8.0
TREND_DOWN_PCT = -8.0
FLUCTUATION_CV = 0.20

# --- Prakiraan omzet ---------------------------------------------------------
FORECAST_HISTORY_DAYS = 28
FORECAST_HORIZON_DAYS = 30


def today() -> date:
    return date.today()
