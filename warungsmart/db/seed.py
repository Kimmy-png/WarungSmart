"""Data simulasi 6 warung + importer CSV.

Pakai:
  python -m warungsmart.db.seed --reset
  python -m warungsmart.db.seed --import-csv path/ke/data.csv

Kolom CSV: tanggal, warung, produk, kategori, qty, harga_jual, harga_beli
           (opsional: jam, stok). Sesuaikan `COLUMN_MAP` jika dataset Anda berbeda.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import timedelta

import numpy as np
import pandas as pd

from warungsmart import config
from warungsmart.db.connection import get_conn, init_db

WARUNG = [
    ("Warung Maju", "Pak Budi"), ("Warung Berkah", "Bu Ani"),
    ("Warung Sumber Rejeki", "Pak Hadi"), ("Warung Bu Siti", "Bu Siti"),
    ("Warung Sejahtera", "Pak Joko"), ("Warung Pak Haji", "Pak Haji"),
]

# nama, kategori, harga_beli, harga_jual, rata-rata unit/hari
CATALOG = [
    ("Mi Instan", "Makanan Instan", 2700, 3000, 7.0),
    ("Air Mineral", "Minuman Dingin", 2200, 3000, 6.0),
    ("Teh Botol Dingin", "Minuman Dingin", 3500, 5000, 4.0),
    ("Kopi Sachet", "Minuman Seduh", 1250, 1500, 5.0),
    ("Gula 1 kg", "Sembako", 15000, 16500, 1.5),
    ("Minyak Goreng 1 L", "Sembako", 16000, 17500, 1.5),
    ("Telur Ayam (butir)", "Sembako", 2100, 2400, 5.0),
    ("Sabun Mandi", "Kebersihan", 3000, 4000, 1.5),
    ("Deterjen Sachet", "Kebersihan", 800, 1000, 3.0),
    ("Snack Ringan", "Camilan", 1800, 2500, 5.0),
    ("Biskuit", "Camilan", 2000, 2500, 3.0),
    ("Jas Hujan Plastik", "Produk Musiman", 4000, 6000, 0.7),
]
HISTORY_DAYS = 90
COLUMN_MAP = {"tanggal": "tanggal", "warung": "warung", "produk": "produk",
              "kategori": "kategori", "qty": "qty",
              "harga_jual": "harga_jual", "harga_beli": "harga_beli"}


def is_empty() -> bool:
    with closing(get_conn()) as c:
        return c.execute("SELECT COUNT(*) FROM warung").fetchone()[0] == 0


def reset() -> None:
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    init_db()


def seed_demo(seed: int = 7) -> None:
    """6 warung x 90 hari, berakhir KEMARIN agar 'hari ini' bisa dicatat saat demo."""
    init_db()
    rng = np.random.default_rng(seed)
    end = config.today() - timedelta(days=1)
    days = pd.date_range(end=end, periods=HISTORY_DAYS)
    t = np.linspace(0, 1, HISTORY_DAYS)
    weekend = np.where(days.dayofweek >= 5, 1.15, 1.0)
    cat_trend = {
        "Minuman Dingin": 1 + 0.35 * t, "Makanan Instan": 1 + 0.18 * t,
        "Sembako": 1 + 0.03 * t, "Produk Musiman": 1 + 0.5 * np.sin(t * 9),
    }
    with closing(get_conn()) as c, c:
        for wi, (nama, pemilik) in enumerate(WARUNG, start=1):
            c.execute("INSERT INTO warung (id, nama, pemilik) VALUES (?,?,?)", (wi, nama, pemilik))
            scale = rng.uniform(0.7, 1.5)
            for pn, kat, beli, jual, base in CATALOG:
                if kat == "Produk Musiman" and wi > 4:      # hanya 4 warung -> uji k-anonimitas
                    continue
                avg = base * scale
                lam = avg * cat_trend.get(kat, np.ones(HISTORY_DAYS)) * weekend
                qty = rng.poisson(np.clip(lam, 0.05, None)).tolist()
                stok = int(avg * rng.uniform(1.5, 14)) + 1
                cur = c.execute(
                    "INSERT INTO produk (warung_id,nama,kategori,harga_beli,harga_jual,stok,stok_min) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (wi, pn, kat, beli, jual, stok, max(3, int(avg * 2))),
                )
                pid = cur.lastrowid
                rows = [(wi, pid, d.date().isoformat(), None, q, float(q * jual), float(q * beli))
                        for d, q in zip(days, qty) if q > 0]
                c.executemany(
                    "INSERT INTO transaksi (warung_id,produk_id,tanggal,jam,qty,total,hpp) "
                    "VALUES (?,?,?,?,?,?,?)", rows)


def import_csv(path: str) -> None:
    """Muat dataset nyata. Jika ada kolom `jam`, disimpan apa adanya (tanpa ubah skema)."""
    init_db()
    df = pd.read_csv(path).rename(columns={v: k for k, v in COLUMN_MAP.items()})
    df["tanggal"] = pd.to_datetime(df["tanggal"]).dt.date.astype(str)
    if "jam" not in df:
        df["jam"] = None
    with closing(get_conn()) as c, c:
        for nama in df["warung"].unique():
            c.execute("INSERT OR IGNORE INTO warung (nama) VALUES (?)", (nama,))
        wid = {r["nama"]: r["id"] for r in c.execute("SELECT id, nama FROM warung")}
        prods = df.groupby(["warung", "produk"]).agg(
            kategori=("kategori", "first"), beli=("harga_beli", "last"), jual=("harga_jual", "last")
        ).reset_index()
        for r in prods.itertuples():
            stok = int(df.loc[(df.warung == r.warung) & (df.produk == r.produk), "stok"].iloc[-1]) \
                if "stok" in df else 0
            c.execute("INSERT OR IGNORE INTO produk (warung_id,nama,kategori,harga_beli,harga_jual,stok) "
                      "VALUES (?,?,?,?,?,?)", (int(wid[r.warung]), r.produk, r.kategori, float(r.beli), float(r.jual), stok))
        pid = {(r["warung_id"], r["nama"]): r["id"]
               for r in c.execute("SELECT id, warung_id, nama FROM produk")}
        rows = [(wid[r.warung], pid[(wid[r.warung], r.produk)], r.tanggal,
                 None if pd.isna(r.jam) else int(r.jam), int(r.qty),
                 float(r.qty * r.harga_jual), float(r.qty * r.harga_beli))
                for r in df.itertuples() if r.qty > 0]
        c.executemany("INSERT INTO transaksi (warung_id,produk_id,tanggal,jam,qty,total,hpp) "
                      "VALUES (?,?,?,?,?,?,?)", rows)


def ensure_seeded() -> None:
    init_db()
    if is_empty():
        seed_demo()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="hapus DB lalu isi data demo")
    ap.add_argument("--import-csv", help="impor dataset CSV ke DB baru")
    a = ap.parse_args()
    if a.import_csv:
        reset(); import_csv(a.import_csv)
    elif a.reset:
        reset(); seed_demo()
    else:
        ensure_seeded()
    print("Database siap:", config.DB_PATH)
