"""Satu-satunya modul yang menjalankan SQL. Service & UI hanya memakai DataFrame."""
from __future__ import annotations

from contextlib import closing
from datetime import date

import pandas as pd

from warungsmart.db.connection import get_conn


# ------------------------------------------------------------------ baca ----
def list_warung() -> pd.DataFrame:
    with closing(get_conn()) as c:
        return pd.read_sql_query("SELECT id, nama, pemilik FROM warung ORDER BY id", c)


def get_products(warung_id: int, only_active: bool = True) -> pd.DataFrame:
    sql = "SELECT * FROM produk WHERE warung_id = ?"
    if only_active:
        sql += " AND aktif = 1"
    with closing(get_conn()) as c:
        return pd.read_sql_query(sql + " ORDER BY nama", c, params=(warung_id,))


_SALES_SQL = """
SELECT t.warung_id, t.produk_id, p.nama AS produk, p.kategori,
       t.tanggal, t.jam, t.qty, t.total, t.hpp, (t.total - t.hpp) AS laba
FROM transaksi t JOIN produk p ON p.id = t.produk_id
"""


def get_sales(warung_id: int | None = None) -> pd.DataFrame:
    """Transaksi mentah (tanggal sebagai datetime). warung_id=None -> semua warung."""
    sql, params = _SALES_SQL, ()
    if warung_id is not None:
        sql, params = sql + " WHERE t.warung_id = ?", (warung_id,)
    with closing(get_conn()) as c:
        df = pd.read_sql_query(sql, c, params=params)
    df["tanggal"] = pd.to_datetime(df["tanggal"])
    return df


def get_daily_entries(warung_id: int, tanggal: date) -> dict[int, int]:
    sql = """SELECT produk_id, SUM(qty) q FROM transaksi
             WHERE warung_id = ? AND tanggal = ? GROUP BY produk_id"""
    with closing(get_conn()) as c:
        rows = c.execute(sql, (warung_id, tanggal.isoformat())).fetchall()
    return {r["produk_id"]: int(r["q"]) for r in rows}


# ----------------------------------------------------------------- tulis ----
def save_daily_sales(warung_id: int, tanggal: date, entries: dict[int, int]) -> int:
    """Simpan catatan harian. Idempotent: mengganti catatan hari itu per produk
    dan menyesuaikan stok sebesar selisihnya. Return jumlah produk yang diubah."""
    iso, changed = tanggal.isoformat(), 0
    with closing(get_conn()) as c, c:
        for pid, qty in entries.items():
            pid, qty = int(pid), max(0, int(qty))
            prod = c.execute(
                "SELECT harga_jual, harga_beli, stok FROM produk WHERE id=? AND warung_id=?",
                (pid, warung_id),
            ).fetchone()
            if prod is None:
                continue
            old = c.execute(
                "SELECT COALESCE(SUM(qty),0) FROM transaksi "
                "WHERE warung_id=? AND produk_id=? AND tanggal=?",
                (warung_id, pid, iso),
            ).fetchone()[0]
            if old == qty:
                continue
            c.execute(
                "DELETE FROM transaksi WHERE warung_id=? AND produk_id=? AND tanggal=?",
                (warung_id, pid, iso),
            )
            if qty > 0:
                c.execute(
                    "INSERT INTO transaksi (warung_id, produk_id, tanggal, jam, qty, total, hpp) "
                    "VALUES (?,?,?,NULL,?,?,?)",
                    (warung_id, pid, iso, qty, qty * prod["harga_jual"], qty * prod["harga_beli"]),
                )
            c.execute("UPDATE produk SET stok = MAX(0, stok - ?) WHERE id=?", (qty - old, pid))
            changed += 1
    return changed


def add_stock(warung_id: int, produk_id: int, qty: int) -> None:
    with closing(get_conn()) as c, c:
        c.execute(
            "UPDATE produk SET stok = stok + ? WHERE id=? AND warung_id=?",
            (int(qty), int(produk_id), int(warung_id)),
        )


def add_product(warung_id: int, nama: str, kategori: str, harga_beli: float,
                harga_jual: float, stok: int = 0, stok_min: int = 5) -> None:
    with closing(get_conn()) as c, c:
        c.execute(
            "INSERT INTO produk (warung_id, nama, kategori, harga_beli, harga_jual, stok, stok_min) "
            "VALUES (?,?,?,?,?,?,?)",
            (warung_id, nama.strip(), kategori.strip(), harga_beli, harga_jual, stok, stok_min),
        )
