import argparse
import csv
import math
import sqlite3
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import NormalDist, mean, stdev

# ============================================================
# UTILITAS
# ============================================================
def rp(n):
    """Format rupiah, contoh: Rp1.250.000 (negatif: -Rp1.250.000)."""
    n = int(round(n))
    teks = "Rp" + format(abs(n), ",").replace(",", ".")
    return "-" + teks if n < 0 else teks


def persen(x, desimal=1):
    return f"{100 * x:.{desimal}f}%"


def tabel(judul, baris, kolom, maks=None):
    """Cetak tabel sederhana. kolom = [(kunci, judul_kolom, fungsi_format_atau_None)]."""
    print(f"\n=== {judul} ===")
    if not baris:
        print("(kosong)")
        return
    data = baris[:maks] if maks else baris
    sel = [[(f(r[k]) if f else str(r[k])) for k, _, f in kolom] for r in data]
    lebar = [max(len(h), *(len(s[i]) for s in sel)) for i, (_, h, _) in enumerate(kolom)]
    print("  ".join(h.ljust(lebar[i]) for i, (_, h, _) in enumerate(kolom)))
    print("  ".join("-" * w for w in lebar))
    for s in sel:
        print("  ".join(v.ljust(lebar[i]) for i, v in enumerate(s)))
    if maks and len(baris) > maks:
        print(f"... ({len(baris) - maks} baris lain)")


def hpp_baru(stok, hpp, qty, harga_beli):
    """HPP rata-rata bergerak. Jika stok habis, HPP = harga beli terbaru."""
    if stok <= 0:
        return float(harga_beli)
    return (stok * hpp + qty * harga_beli) / (stok + qty)


# ============================================================
# BAGIAN A1 - SKEMA DATABASE
# ============================================================
SKEMA = """
CREATE TABLE IF NOT EXISTS produk (
    warung_id  TEXT NOT NULL,
    produk     TEXT NOT NULL,
    kategori   TEXT NOT NULL DEFAULT 'Lainnya',
    stok       INTEGER NOT NULL DEFAULT 0,
    hpp        REAL NOT NULL DEFAULT 0,
    harga_jual INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (warung_id, produk)
);
CREATE TABLE IF NOT EXISTS transaksi (
    trx_id    TEXT PRIMARY KEY,
    warung_id TEXT NOT NULL,
    tanggal   TEXT NOT NULL,
    jam       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS item_transaksi (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    trx_id     TEXT NOT NULL REFERENCES transaksi(trx_id),
    warung_id  TEXT NOT NULL,
    tanggal    TEXT NOT NULL,
    jam        TEXT NOT NULL,
    produk     TEXT NOT NULL,
    jumlah     INTEGER NOT NULL CHECK (jumlah > 0),
    harga_jual INTEGER NOT NULL,
    hpp        REAL NOT NULL            -- HPP saat barang dijual (untuk COGS)
);
CREATE TABLE IF NOT EXISTS pembelian (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    warung_id  TEXT NOT NULL,
    tanggal    TEXT NOT NULL,
    produk     TEXT NOT NULL,
    jumlah     INTEGER NOT NULL CHECK (jumlah > 0),
    harga_beli INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS kas_lain (       -- modal, biaya operasional, prive
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    warung_id  TEXT NOT NULL,
    tanggal    TEXT NOT NULL,
    jenis      TEXT NOT NULL CHECK (jenis IN ('MODAL','BIAYA','PRIVE')),
    keterangan TEXT NOT NULL DEFAULT '',
    jumlah     INTEGER NOT NULL CHECK (jumlah > 0)
);
CREATE TABLE IF NOT EXISTS stockout (        -- permintaan yang hilang karena stok habis
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    warung_id     TEXT NOT NULL,
    tanggal       TEXT NOT NULL,
    jam           TEXT NOT NULL,
    produk        TEXT NOT NULL,
    jumlah_hilang INTEGER NOT NULL,
    disubstitusi  INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_item_w_tgl  ON item_transaksi (warung_id, tanggal);
CREATE INDEX IF NOT EXISTS ix_item_w_prod ON item_transaksi (warung_id, produk, tanggal);
CREATE INDEX IF NOT EXISTS ix_beli_w_tgl  ON pembelian (warung_id, tanggal);
CREATE INDEX IF NOT EXISTS ix_kas_w_tgl   ON kas_lain (warung_id, tanggal);
CREATE INDEX IF NOT EXISTS ix_so_w_prod   ON stockout (warung_id, produk, tanggal);
"""


def buka_db(path="warungsmart.db"):
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SKEMA)
    return con


# ============================================================
# BAGIAN A2 - PENCATATAN TRANSAKSI (dipakai aplikasi secara langsung)
# ============================================================
def catat_pembelian(con, warung_id, tanggal, produk, jumlah, harga_beli,
                    kategori="Lainnya", komit=True):
    """Barang masuk: menambah stok dan memperbarui HPP rata-rata bergerak."""
    if jumlah <= 0 or harga_beli <= 0:
        raise ValueError("jumlah dan harga_beli harus > 0")
    r = con.execute("SELECT stok, hpp FROM produk WHERE warung_id=? AND produk=?",
                    (warung_id, produk)).fetchone()
    if r is None:
        con.execute("INSERT INTO produk (warung_id, produk, kategori, stok, hpp, harga_jual) "
                    "VALUES (?,?,?,?,?,0)", (warung_id, produk, kategori, jumlah, harga_beli))
    else:
        stok, hpp = r
        con.execute("UPDATE produk SET stok=?, hpp=? WHERE warung_id=? AND produk=?",
                    (stok + jumlah, hpp_baru(stok, hpp, jumlah, harga_beli), warung_id, produk))
    con.execute("INSERT INTO pembelian (warung_id, tanggal, produk, jumlah, harga_beli) "
                "VALUES (?,?,?,?,?)", (warung_id, tanggal, produk, jumlah, harga_beli))
    if komit:
        con.commit()


def catat_penjualan(con, warung_id, tanggal, jam, items, trx_id=None, komit=True):
    """
    Satu nota penjualan. items = [(produk, jumlah) atau (produk, jumlah, harga_jual), ...]
    Semua item divalidasi dulu; jika ada yang gagal, tidak ada yang tersimpan.
    Mengembalikan trx_id.
    """
    if not items:
        raise ValueError("nota kosong")
    sisa, baris = {}, []
    for it in items:
        produk, jumlah = it[0], int(it[1])
        r = con.execute("SELECT stok, hpp, harga_jual FROM produk WHERE warung_id=? AND produk=?",
                        (warung_id, produk)).fetchone()
        if r is None:
            raise ValueError(f"produk '{produk}' belum terdaftar")
        if jumlah <= 0:
            raise ValueError("jumlah harus > 0")
        stok, hpp, harga_default = r
        stok = sisa.get(produk, stok)
        if jumlah > stok:
            raise ValueError(f"stok '{produk}' tidak cukup (sisa {stok}, diminta {jumlah})")
        harga = int(it[2]) if len(it) > 2 and it[2] is not None else harga_default
        if harga <= 0:
            raise ValueError(f"harga jual '{produk}' belum diatur")
        sisa[produk] = stok - jumlah
        baris.append((produk, jumlah, harga, hpp))

    if trx_id is None:
        n = con.execute("SELECT COUNT(*) FROM transaksi WHERE warung_id=? AND tanggal=?",
                        (warung_id, tanggal)).fetchone()[0] + 1
        trx_id = f"{warung_id}-{tanggal.replace('-', '')}-{n:04d}"
    con.execute("INSERT INTO transaksi (trx_id, warung_id, tanggal, jam) VALUES (?,?,?,?)",
                (trx_id, warung_id, tanggal, jam))
    for produk, jumlah, harga, hpp in baris:
        con.execute("INSERT INTO item_transaksi (trx_id, warung_id, tanggal, jam, produk, "
                    "jumlah, harga_jual, hpp) VALUES (?,?,?,?,?,?,?,?)",
                    (trx_id, warung_id, tanggal, jam, produk, jumlah, harga, hpp))
        con.execute("UPDATE produk SET stok = stok - ?, harga_jual = ? "
                    "WHERE warung_id=? AND produk=?", (jumlah, harga, warung_id, produk))
    if komit:
        con.commit()
    return trx_id


def catat_kas_lain(con, warung_id, tanggal, jenis, jumlah, keterangan="", komit=True):
    """jenis: MODAL (setoran modal), BIAYA (operasional), PRIVE (pengambilan pribadi)."""
    con.execute("INSERT INTO kas_lain (warung_id, tanggal, jenis, keterangan, jumlah) "
                "VALUES (?,?,?,?,?)", (warung_id, tanggal, jenis.upper(), keterangan, int(jumlah)))
    if komit:
        con.commit()


# ============================================================
# IMPOR DATA SIMULASI (luaran warung_abm.py) -> database
# ============================================================
def impor_simulasi(con, folder, warung_ids=None):
    """
    Memutar ulang pembelian & penjualan secara kronologis (pembelian pagi lebih dulu),
    menghitung HPP sendiri, lalu memasukkannya ke database. Mengembalikan laporan impor.
    """
    folder = Path(folder)

    def baca(nama):
        with open(folder / nama, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    jual_semua, beli_semua = baca("penjualan.csv"), baca("pembelian.csv")
    so_semua = baca("stockout.csv") if (folder / "stockout.csv").exists() else []
    ids = warung_ids or sorted({r["warung_id"] for r in jual_semua})
    laporan = {}

    for wid in ids:
        for tbl in ("item_transaksi", "transaksi", "pembelian", "kas_lain", "stockout", "produk"):
            con.execute(f"DELETE FROM {tbl} WHERE warung_id=?", (wid,))
        beli = [r for r in beli_semua if r["warung_id"] == wid]
        jual = [r for r in jual_semua if r["warung_id"] == wid]
        state = {}                      # produk -> [stok, hpp, kategori, harga_jual]
        rows_beli, rows_trx, rows_item = [], [], []
        seen, selisih_stok, i = set(), 0, 0

        def proses_beli(r):
            p, q, h = r["produk"], int(r["jumlah"]), int(r["harga_beli"])
            s = state.setdefault(p, [0, 0.0, r["kategori"], 0])
            s[1] = hpp_baru(s[0], s[1], q, h)
            s[0] += q
            rows_beli.append((wid, r["tanggal"], p, q, h))

        for r in jual:
            while i < len(beli) and beli[i]["tanggal"] <= r["tanggal"]:
                proses_beli(beli[i])
                i += 1
            s = state[r["produk"]]
            q, hj = int(r["jumlah"]), int(r["harga_jual"])
            if q > s[0]:
                raise ValueError(f"stok negatif untuk {r['produk']} pada {r['tanggal']}")
            if r["trx_id"] not in seen:
                seen.add(r["trx_id"])
                rows_trx.append((r["trx_id"], wid, r["tanggal"], r["jam"]))
            rows_item.append((r["trx_id"], wid, r["tanggal"], r["jam"], r["produk"], q, hj, s[1]))
            s[0] -= q
            s[3] = hj
            if s[0] != int(r["stok_akhir"]):
                selisih_stok += 1
        while i < len(beli):
            proses_beli(beli[i])
            i += 1

        con.executemany("INSERT INTO transaksi VALUES (?,?,?,?)", rows_trx)
        con.executemany("INSERT INTO item_transaksi (trx_id, warung_id, tanggal, jam, produk, "
                        "jumlah, harga_jual, hpp) VALUES (?,?,?,?,?,?,?,?)", rows_item)
        con.executemany("INSERT INTO pembelian (warung_id, tanggal, produk, jumlah, harga_beli) "
                        "VALUES (?,?,?,?,?)", rows_beli)
        con.executemany("INSERT INTO produk VALUES (?,?,?,?,?,?)",
                        [(wid, p, s[2], s[0], s[1], s[3]) for p, s in state.items()])
        con.executemany("INSERT INTO stockout (warung_id, tanggal, jam, produk, jumlah_hilang, "
                        "disubstitusi) VALUES (?,?,?,?,?,?)",
                        [(r["warung_id"], r["tanggal"], r["jam"], r["produk"],
                          int(r["jumlah_hilang"]), int(r["disubstitusi"])) for r in so_semua if r["warung_id"] == wid])
        con.commit()
        laporan[wid] = dict(item=len(rows_item), transaksi=len(rows_trx),
                            pembelian=len(rows_beli), produk=len(state),
                            selisih_stok=selisih_stok)
    return laporan


# ============================================================
# BANTUAN RENTANG TANGGAL
# ============================================================
def tanggal_terakhir(con, warung_id):
    return con.execute("SELECT MAX(tanggal) FROM item_transaksi WHERE warung_id=?",
                       (warung_id,)).fetchone()[0]


def tanggal_pertama(con, warung_id):
    r = con.execute("SELECT MIN(t) FROM (SELECT MIN(tanggal) t FROM item_transaksi WHERE warung_id=? "
                    "UNION ALL SELECT MIN(tanggal) FROM pembelian WHERE warung_id=?)",
                    (warung_id, warung_id)).fetchone()
    return r[0]


def _rentang(con, warung_id, dari=None, sampai=None, hari=None):
    sampai = sampai or tanggal_terakhir(con, warung_id)
    if dari is None:
        if hari:
            dari = (date.fromisoformat(sampai) - timedelta(days=hari - 1)).isoformat()
        else:
            dari = tanggal_pertama(con, warung_id)
    return dari, sampai


def _jumlah_hari(dari, sampai):
    return (date.fromisoformat(sampai) - date.fromisoformat(dari)).days + 1


# ============================================================
# BAGIAN A3 - MARGIN, LABA RUGI, ARUS KAS, PERSEDIAAN
# ============================================================
def analisis_margin(con, warung_id, margin_min=0.10):
    """Margin per produk berdasar harga jual terakhir dan HPP saat ini."""
    hasil = []
    for p, kat, stok, hpp, jual in con.execute(
            "SELECT produk, kategori, stok, hpp, harga_jual FROM produk "
            "WHERE warung_id=? AND harga_jual>0", (warung_id,)):
        margin = jual - hpp
        m = margin / jual
        flag = "RUGI" if margin < 0 else ("TIPIS" if m < margin_min else "")
        hasil.append(dict(produk=p, kategori=kat, stok=stok, hpp=hpp, harga_jual=jual,
                          margin_rp=margin, margin_persen=m,
                          markup_persen=margin / hpp if hpp else 0, catatan=flag))
    return sorted(hasil, key=lambda r: r["margin_persen"])


def laporan_laba_rugi(con, warung_id, dari=None, sampai=None, hari=None):
    dari, sampai = _rentang(con, warung_id, dari, sampai, hari)
    omzet, hpp_terjual = con.execute(
        "SELECT COALESCE(SUM(jumlah*harga_jual),0), COALESCE(SUM(jumlah*hpp),0) "
        "FROM item_transaksi WHERE warung_id=? AND tanggal BETWEEN ? AND ?",
        (warung_id, dari, sampai)).fetchone()
    biaya = con.execute(
        "SELECT keterangan, SUM(jumlah) FROM kas_lain WHERE warung_id=? AND jenis='BIAYA' "
        "AND tanggal BETWEEN ? AND ? GROUP BY keterangan ORDER BY 2 DESC",
        (warung_id, dari, sampai)).fetchall()
    prive = con.execute(
        "SELECT COALESCE(SUM(jumlah),0) FROM kas_lain WHERE warung_id=? AND jenis='PRIVE' "
        "AND tanggal BETWEEN ? AND ?", (warung_id, dari, sampai)).fetchone()[0]
    total_biaya = sum(j for _, j in biaya)
    laba_kotor = omzet - hpp_terjual
    laba_bersih = laba_kotor - total_biaya
    return dict(dari=dari, sampai=sampai, omzet=omzet, hpp=hpp_terjual, laba_kotor=laba_kotor,
                margin_kotor=laba_kotor / omzet if omzet else 0, biaya=biaya,
                total_biaya=total_biaya, laba_bersih=laba_bersih,
                margin_bersih=laba_bersih / omzet if omzet else 0,
                prive=prive, laba_ditahan=laba_bersih - prive)


def cetak_laba_rugi(lr):
    print(f"\n=== LAPORAN LABA RUGI  {lr['dari']} s.d. {lr['sampai']} ===")
    print(f"Penjualan (omzet)          {rp(lr['omzet']):>16}")
    print(f"HPP barang terjual         {rp(-lr['hpp']):>16}")
    print(f"Laba kotor                 {rp(lr['laba_kotor']):>16}  ({persen(lr['margin_kotor'])})")
    for ket, jml in lr["biaya"]:
        print(f"  Biaya: {ket:<18}{rp(-jml):>16}")
    print(f"Laba bersih                {rp(lr['laba_bersih']):>16}  ({persen(lr['margin_bersih'])})")
    print(f"Pengambilan pribadi (prive){rp(-lr['prive']):>16}   <- bukan biaya usaha")
    print(f"Laba yang tetap di usaha   {rp(lr['laba_ditahan']):>16}")


def _total_arus(con, warung_id, dari=None, sampai=None):
    """Total arus kas per komponen pada rentang tanggal (None = tanpa batas)."""
    kond, par = "warung_id=?", [warung_id]
    if dari:
        kond += " AND tanggal>=?"
        par.append(dari)
    if sampai:
        kond += " AND tanggal<=?"
        par.append(sampai)
    q = lambda sql: con.execute(sql.format(kond=kond), par).fetchone()[0] or 0
    kas = lambda j: q("SELECT SUM(jumlah) FROM kas_lain WHERE {kond} AND jenis='%s'" % j)
    return dict(penjualan=q("SELECT SUM(jumlah*harga_jual) FROM item_transaksi WHERE {kond}"),
                pembelian=q("SELECT SUM(jumlah*harga_beli) FROM pembelian WHERE {kond}"),
                modal=kas("MODAL"), biaya=kas("BIAYA"), prive=kas("PRIVE"))


def _kas(a):
    return a["penjualan"] + a["modal"] - a["pembelian"] - a["biaya"] - a["prive"]


def laporan_arus_kas(con, warung_id, dari=None, sampai=None):
    """Arus kas bulanan: kas masuk, kas keluar, saldo."""
    dari, sampai = _rentang(con, warung_id, dari, sampai)
    per = defaultdict(lambda: dict(penjualan=0, pembelian=0, modal=0, biaya=0, prive=0))
    for kunci, tbl, ekspr, jenis in [
            ("penjualan", "item_transaksi", "jumlah*harga_jual", None),
            ("pembelian", "pembelian", "jumlah*harga_beli", None),
            ("modal", "kas_lain", "jumlah", "MODAL"),
            ("biaya", "kas_lain", "jumlah", "BIAYA"),
            ("prive", "kas_lain", "jumlah", "PRIVE")]:
        sql = (f"SELECT strftime('%Y-%m', tanggal), SUM({ekspr}) FROM {tbl} "
               f"WHERE warung_id=? AND tanggal BETWEEN ? AND ?")
        if jenis:
            sql += f" AND jenis='{jenis}'"
        for bln, jml in con.execute(sql + " GROUP BY 1", (warung_id, dari, sampai)):
            per[bln][kunci] = jml or 0
    saldo = _kas(_total_arus(con, warung_id, sampai=(date.fromisoformat(dari)
                                                     - timedelta(days=1)).isoformat()))
    hasil = []
    for bln in sorted(per):
        a = per[bln]
        masuk, keluar = a["penjualan"] + a["modal"], a["pembelian"] + a["biaya"] + a["prive"]
        saldo_awal, saldo = saldo, saldo + masuk - keluar
        hasil.append(dict(bulan=bln, saldo_awal=saldo_awal, penjualan=a["penjualan"],
                          modal=a["modal"], beli_stok=a["pembelian"], biaya=a["biaya"],
                          prive=a["prive"], arus_bersih=masuk - keluar, saldo_akhir=saldo))
    return hasil


def nilai_persediaan(con, warung_id):
    """Nilai persediaan saat ini = stok x HPP, total dan per kategori."""
    per_kat = con.execute(
        "SELECT kategori, SUM(stok), SUM(stok*hpp) FROM produk WHERE warung_id=? "
        "GROUP BY kategori ORDER BY 3 DESC", (warung_id,)).fetchall()
    return dict(total=sum(n for _, _, n in per_kat), unit=sum(u for _, u, _ in per_kat),
                per_kategori=[dict(kategori=k, unit=u, nilai=n) for k, u, n in per_kat])


def posisi_keuangan(con, warung_id):
    """Ringkasan pemisah modal, laba, prive, kas, dan persediaan (sepanjang waktu)."""
    a = _total_arus(con, warung_id)
    cogs = con.execute("SELECT COALESCE(SUM(jumlah*hpp),0) FROM item_transaksi WHERE warung_id=?",
                       (warung_id,)).fetchone()[0]
    laba_bersih = a["penjualan"] - cogs - a["biaya"]
    persediaan = nilai_persediaan(con, warung_id)["total"]
    kas = _kas(a)
    return dict(modal=a["modal"], laba_bersih=laba_bersih, prive=a["prive"],
                ekuitas=a["modal"] + laba_bersih - a["prive"], kas=kas,
                persediaan=persediaan, aset=kas + persediaan)


def cek_integritas(con, warung_id):
    """Pemeriksaan otomatis. Semua harus lulus agar laporan dapat dipercaya."""
    pk = posisi_keuangan(con, warung_id)
    a = _total_arus(con, warung_id)
    cogs = con.execute("SELECT COALESCE(SUM(jumlah*hpp),0) FROM item_transaksi WHERE warung_id=?",
                       (warung_id,)).fetchone()[0]
    neg = con.execute("SELECT COUNT(*) FROM produk WHERE warung_id=? AND stok<0",
                      (warung_id,)).fetchone()[0]
    jual_rugi = con.execute("SELECT COUNT(*) FROM item_transaksi WHERE warung_id=? "
                            "AND harga_jual<hpp", (warung_id,)).fetchone()[0]
    cek = [
        ("Aset (kas + persediaan) = modal + laba - prive",
         abs(pk["aset"] - pk["ekuitas"]) < 1, f"selisih {rp(pk['aset'] - pk['ekuitas'])}"),
        ("Persediaan = total pembelian - HPP terjual",
         abs(pk["persediaan"] - (a["pembelian"] - cogs)) < 1,
         f"selisih {rp(pk['persediaan'] - (a['pembelian'] - cogs))}"),
        ("Tidak ada stok negatif", neg == 0, f"{neg} produk"),
    ]
    info = f"info: {jual_rugi} baris terjual di bawah HPP (penjualan rugi)"
    return cek, info


# ============================================================
# BAGIAN B1 - PRODUK TERLARIS & ANALISIS ABC
# ============================================================
def produk_terlaris(con, warung_id, hari=30, sampai=None, urut="jumlah", n=10):
    """urut: 'jumlah' (unit), 'omzet', atau 'laba'."""
    ekspr = {"jumlah": "SUM(jumlah)", "omzet": "SUM(jumlah*harga_jual)",
             "laba": "SUM(jumlah*(harga_jual-hpp))"}[urut]
    dari, sampai = _rentang(con, warung_id, None, sampai, hari)
    rows = con.execute(
        f"SELECT produk, SUM(jumlah), SUM(jumlah*harga_jual), SUM(jumlah*(harga_jual-hpp)) "
        f"FROM item_transaksi WHERE warung_id=? AND tanggal BETWEEN ? AND ? "
        f"GROUP BY produk ORDER BY {ekspr} DESC, produk LIMIT ?",
        (warung_id, dari, sampai, n)).fetchall()
    return [dict(peringkat=i, produk=p, unit=q, omzet=o, laba=l)
            for i, (p, q, o, l) in enumerate(rows, 1)]


def analisis_abc(con, warung_id, hari=90, sampai=None, batas_a=0.80, batas_b=0.95, dasar="omzet"):
    """
    Pareto: urutkan berdasar omzet (atau laba), lalu beri kelas dari porsi kumulatif
    SEBELUM produk itu ditambahkan: < 80% -> A, < 95% -> B, sisanya C.
    Produk tanpa penjualan pada periode otomatis kelas C.
    """
    ekspr = {"omzet": "jumlah*harga_jual", "laba": "jumlah*(harga_jual-hpp)"}[dasar]
    dari, sampai = _rentang(con, warung_id, None, sampai, hari)
    nilai = dict(con.execute(
        f"SELECT produk, SUM({ekspr}) FROM item_transaksi WHERE warung_id=? "
        f"AND tanggal BETWEEN ? AND ? GROUP BY produk", (warung_id, dari, sampai)))
    semua = [r[0] for r in con.execute("SELECT produk FROM produk WHERE warung_id=?", (warung_id,))]
    daftar = sorted(((p, nilai.get(p, 0)) for p in semua), key=lambda x: (-x[1], x[0]))
    total = sum(v for _, v in daftar) or 1
    kum, hasil = 0, []
    for i, (p, v) in enumerate(daftar, 1):
        before = kum / total
        kelas = "C" if v <= 0 else ("A" if before < batas_a else "B" if before < batas_b else "C")
        kum += v
        hasil.append(dict(peringkat=i, produk=p, nilai=v, porsi=v / total,
                          kumulatif=kum / total, kelas=kelas))
    return hasil


def ringkas_abc(hasil):
    out = {}
    for k in "ABC":
        sub = [r for r in hasil if r["kelas"] == k]
        out[k] = dict(jumlah=len(sub), porsi_produk=len(sub) / len(hasil),
                      porsi_nilai=sum(r["porsi"] for r in sub))
    return out


# ============================================================
# BAGIAN B2 - SAFETY STOCK, REORDER POINT, PERINGATAN STOK
# ============================================================
def _permintaan_harian(con, warung_id, dari, sampai, koreksi_stockout=True, produk=None):
    """Permintaan harian per produk (hari tanpa penjualan dihitung 0).
    Jika koreksi_stockout, permintaan yang hilang karena stok habis ditambahkan kembali."""
    n = _jumlah_hari(dari, sampai)
    idx = {(date.fromisoformat(dari) + timedelta(days=i)).isoformat(): i for i in range(n)}
    seri = defaultdict(lambda: [0] * n)
    filt, par = ("AND produk=?", [produk]) if produk else ("", [])
    sumber = [("SELECT produk, tanggal, SUM(jumlah) FROM item_transaksi "
               "WHERE warung_id=? AND tanggal BETWEEN ? AND ? %s GROUP BY produk, tanggal")]
    if koreksi_stockout:
        sumber.append("SELECT produk, tanggal, SUM(jumlah_hilang) FROM stockout "
                      "WHERE warung_id=? AND tanggal BETWEEN ? AND ? %s GROUP BY produk, tanggal")
    for sql in sumber:
        for p, tgl, q in con.execute(sql % filt, [warung_id, dari, sampai] + par):
            seri[p][idx[tgl]] += q
    return seri, n


def reorder_point(con, warung_id, hari_data=28, sampai=None, lead_time=2,
                  tingkat_layanan=0.95, review=1, koreksi_stockout=True, hari_berlebih=45):
    """
    lead_time: hari (angka) atau dict {kategori: hari, 'default': hari}.
    Hasil diurutkan dari yang paling mendesak.
    """
    dari, sampai = _rentang(con, warung_id, None, sampai, hari_data)
    seri, n = _permintaan_harian(con, warung_id, dari, sampai, koreksi_stockout)
    z = NormalDist().inv_cdf(tingkat_layanan)
    urutan = {"HABIS": 0, "PESAN SEKARANG": 1, "WASPADA": 2, "AMAN": 3,
              "BERLEBIH": 4, "TIDAK LAKU": 5}
    hasil = []
    for p, kat, stok in con.execute("SELECT produk, kategori, stok FROM produk WHERE warung_id=?",
                                    (warung_id,)):
        L = lead_time.get(kat, lead_time.get("default", 2)) if isinstance(lead_time, dict) \
            else lead_time
        s = seri.get(p, [0] * n)
        d = mean(s)
        sd = stdev(s) if n > 1 else 0.0
        ss = z * sd * math.sqrt(L)
        rop = d * L + ss
        target = d * (L + review) + ss
        if d > 0:
            rop, target = max(1, math.ceil(rop)), max(1, math.ceil(target))
        else:
            rop, target = 0, 0
        hari_stok = stok / d if d > 0 else float("inf")
        if d == 0:
            status = "TIDAK LAKU" if stok > 0 else "AMAN"
        elif stok <= 0:
            status = "HABIS"
        elif stok <= rop:
            status = "PESAN SEKARANG"
        elif stok <= rop * 1.25 or hari_stok <= L + review:
            status = "WASPADA"
        elif hari_stok > hari_berlebih:
            status = "BERLEBIH"
        else:
            status = "AMAN"
        saran = max(0, target - stok) if status in ("HABIS", "PESAN SEKARANG", "WASPADA") else 0
        hasil.append(dict(produk=p, kategori=kat, stok=stok, rata_harian=d, sigma=sd,
                          safety_stock=math.ceil(ss) if d > 0 else 0, rop=rop, target=target,
                          hari_stok=hari_stok, status=status, saran_pesan=saran))
    return sorted(hasil, key=lambda r: (urutan[r["status"]], r["hari_stok"], r["produk"]))


def peringatan_stok(rop_hasil):
    """Aturan if-then: hanya yang perlu tindakan pembelian."""
    return [r for r in rop_hasil if r["status"] in ("HABIS", "PESAN SEKARANG", "WASPADA")]


# ============================================================
# BAGIAN B3 - SIMULASI HARGA
# ============================================================
def simulasi_harga(con, warung_id, produk, harga_baru, hari_data=28, sampai=None,
                   elastisitas=(0.0, 0.5, 1.0, 1.5), koreksi_stockout=True):
    """
    Volume baru = volume lama x (harga baru / harga lama) ^ (-elastisitas).
    elastisitas 0 = 'harga baru x volume tetap' (versi paling sederhana).
    Juga menghitung batas penurunan volume sebelum laba harian turun.
    """
    r = con.execute("SELECT harga_jual, hpp FROM produk WHERE warung_id=? AND produk=?",
                    (warung_id, produk)).fetchone()
    if r is None or r[0] <= 0:
        raise ValueError("produk tidak ditemukan / belum punya harga jual")
    p0, hpp = r
    dari, sampai = _rentang(con, warung_id, None, sampai, hari_data)
    seri, n = _permintaan_harian(con, warung_id, dari, sampai, koreksi_stockout, produk)
    v0 = mean(seri[produk]) if produk in seri else 0.0
    laba0 = (p0 - hpp) * v0
    margin_baru = harga_baru - hpp
    skenario = []
    for e in elastisitas:
        v1 = v0 * (harga_baru / p0) ** (-e)
        laba1 = margin_baru * v1
        skenario.append(dict(elastisitas=e, volume=v1, laba_harian=laba1, selisih=laba1 - laba0,
                             perubahan_volume=(v1 / v0 - 1) if v0 else 0))
    if margin_baru > 0 and p0 - hpp > 0:
        batas = 1 - (p0 - hpp) / margin_baru       # volume boleh turun sebesar ini
    else:
        batas = None
    return dict(produk=produk, harga_lama=p0, harga_baru=harga_baru, hpp=hpp,
                margin_lama=(p0 - hpp) / p0, margin_baru=margin_baru / harga_baru,
                volume_lama=v0, laba_harian_lama=laba0, skenario=skenario,
                batas_penurunan_volume=batas)


# ============================================================
# DEMO KAS (contoh modal/biaya/prive; HANYA untuk data simulasi)
# ============================================================
def siapkan_demo_kas(con, warung_id):
    """Mengisi modal awal, biaya bulanan, dan prive contoh agar laporan kas lengkap."""
    if con.execute("SELECT COUNT(*) FROM kas_lain WHERE warung_id=?", (warung_id,)).fetchone()[0]:
        return False
    awal = tanggal_pertama(con, warung_id)
    beli_awal = con.execute("SELECT SUM(jumlah*harga_beli) FROM pembelian "
                            "WHERE warung_id=? AND tanggal=?", (warung_id, awal)).fetchone()[0]
    modal = math.ceil(beli_awal * 1.3 / 1_000_000) * 1_000_000
    catat_kas_lain(con, warung_id, awal, "MODAL", modal, "Modal awal (contoh)", komit=False)
    akhir = tanggal_terakhir(con, warung_id)
    bulan = [r[0] for r in con.execute(
        "SELECT DISTINCT strftime('%Y-%m', tanggal) FROM item_transaksi WHERE warung_id=? "
        "ORDER BY 1", (warung_id,))]
    for b in bulan:
        if f"{b}-05" > awal and f"{b}-05" <= akhir:
            catat_kas_lain(con, warung_id, f"{b}-05", "BIAYA", 350_000, "Listrik", komit=False)
            catat_kas_lain(con, warung_id, f"{b}-05", "BIAYA", 200_000, "Kebersihan & lain-lain",
                           komit=False)
        lk = con.execute("SELECT SUM(jumlah*(harga_jual-hpp)) FROM item_transaksi "
                         "WHERE warung_id=? AND strftime('%Y-%m', tanggal)=?", (warung_id, b)).fetchone()[0] or 0
        tgl_prive = f"{b}-28"
        if awal < tgl_prive <= akhir and lk > 0:
            catat_kas_lain(con, warung_id, tgl_prive, "PRIVE",
                           int(lk * 0.5 // 100_000 * 100_000), "Ambil pribadi (50% laba kotor, contoh)",
                           komit=False)
    con.commit()
    return True


# ============================================================
# DEMO / CLI
# ============================================================
def main():
    ap = argparse.ArgumentParser(description="WarungSmart Core - demo laporan & analitik")
    ap.add_argument("--data", default="data_simulasi", help="folder luaran warung_abm.py")
    ap.add_argument("--db", default="warungsmart.db")
    ap.add_argument("--warung", default="W2")
    ap.add_argument("--hari", type=int, default=30, help="jendela laporan/analisis (hari)")
    ap.add_argument("--impor", action="store_true", help="paksa impor ulang data simulasi")
    ap.add_argument("--demo", action="store_true", help="isi modal/biaya/prive contoh + demo catat")

    # Modify this line to handle unrecognized arguments
    args, unknown = ap.parse_known_args()

    con = buka_db(args.db)
    ada = con.execute("SELECT COUNT(*) FROM item_transaksi WHERE warung_id=?", (args.warung,)).fetchone()[0]
    if args.impor or not ada:
        lap = impor_simulasi(con, args.data, [args.warung])[args.warung]
        print(f"Impor {args.warung}: {lap['item']:,} item, {lap['transaksi']:,} nota, "
              f"{lap['pembelian']:,} pembelian, {lap['produk']} produk | "
              f"selisih stok vs simulasi: {lap['selisih_stok']}")
    if args.demo and siapkan_demo_kas(con, args.warung):
        print("Modal, biaya, dan prive CONTOH diisi (data simulasi).")

    w = args.warung
    # --- A. Deterministik ---
    cetak_laba_rugi(laporan_laba_rugi(con, w, hari=args.hari))

    kas = laporan_arus_kas(con, w)
    tabel("ARUS KAS BULANAN", kas, [
        ("bulan", "Bulan", None), ("saldo_awal", "Saldo awal", rp), ("penjualan", "Penjualan", rp),
        ("beli_stok", "Beli stok", rp), ("biaya", "Biaya", rp), ("prive", "Prive", rp),
        ("saldo_akhir", "Saldo akhir", rp)], maks=6)

    nv = nilai_persediaan(con, w)
    tabel(f"NILAI PERSEDIAAN (total {rp(nv['total'])}, {nv['unit']:,} unit)", nv["per_kategori"],
          [("kategori", "Kategori", None), ("unit", "Unit", None), ("nilai", "Nilai", rp)], maks=6)

    pk = posisi_keuangan(con, w)
    print("\n=== POSISI KEUANGAN (sepanjang waktu) ===")
    print(f"Modal disetor {rp(pk['modal'])} + laba bersih {rp(pk['laba_bersih'])} "
          f"- prive {rp(pk['prive'])} = {rp(pk['ekuitas'])}")
    print(f"Kas {rp(pk['kas'])} + persediaan {rp(pk['persediaan'])} = {rp(pk['aset'])}")

    cek, info = cek_integritas(con, w)
    print("\n=== CEK INTEGRITAS ===")
    for nama, ok, det in cek:
        print(f"[{'LULUS' if ok else 'GAGAL'}] {nama} ({det})")
    print(info)

    mg = analisis_margin(con, w, margin_min=0.08)
    tabel("MARGIN TERTIPIS", mg, [
        ("produk", "Produk", None), ("harga_jual", "Jual", rp), ("hpp", "HPP", rp),
        ("margin_persen", "Margin", persen), ("catatan", "Catatan", None)], maks=6)

    # --- B. Statistik & aturan ---
    tabel(f"PRODUK TERLARIS ({args.hari} hari, unit)", produk_terlaris(con, w, args.hari), [
        ("peringkat", "#", None), ("produk", "Produk", None), ("unit", "Unit", None),
        ("omzet", "Omzet", rp), ("laba", "Laba kotor", rp)])

    abc = analisis_abc(con, w, hari=90)
    print("\n=== ANALISIS ABC (omzet 90 hari) ===")
    for k, v in ringkas_abc(abc).items():
        print(f"Kelas {k}: {v['jumlah']:>3} produk ({persen(v['porsi_produk'], 0)} produk) "
              f"-> {persen(v['porsi_nilai'], 0)} omzet")

    rop = reorder_point(con, w, hari_data=28, lead_time={"default": 2, "Frozen": 1, "LPG": 3})
    hitung = defaultdict(int)
    for r in rop:
        hitung[r["status"]] += 1
    print("\n=== STATUS STOK === " + " | ".join(f"{k}: {v}" for k, v in hitung.items()))
    tabel("PERINGATAN STOK (perlu tindakan)", peringatan_stok(rop), [
        ("produk", "Produk", None), ("stok", "Stok", None),
        ("rata_harian", "Rata2/hari", lambda x: f"{x:.1f}"), ("safety_stock", "SS", None),
        ("rop", "ROP", None), ("status", "Status", None), ("saran_pesan", "Saran pesan", None)], maks=10)

    top = produk_terlaris(con, w, args.hari, n=1)[0]["produk"]
    p0 = con.execute("SELECT harga_jual FROM produk WHERE warung_id=? AND produk=?", (w, top)).fetchone()[0]
    sim = simulasi_harga(con, w, top, int(round(p0 * 1.10 / 100) * 100))
    print(f"\n=== SIMULASI HARGA: {top} ===")
    print(f"Harga {rp(sim['harga_lama'])} -> {rp(sim['harga_baru'])} | HPP {rp(sim['hpp'])} | "
          f"margin {persen(sim['margin_lama'])} -> {persen(sim['margin_baru'])}")
    print(f"Volume saat ini {sim['volume_lama']:.1f}/hari | laba kotor {rp(sim['laba_harian_lama'])}/hari")
    if sim["batas_penurunan_volume"] is not None:
        print(f"Kenaikan harga masih menguntungkan selama volume tidak turun lebih dari "
              f"{persen(sim['batas_penurunan_volume'])}")
    for s in sim["skenario"]:
        print(f"  elastisitas {s['elastisitas']:.1f}: volume {s['volume']:.1f}/hari "
              f"({s['perubahan_volume']:+.0%}) | laba {rp(s['laba_harian'])}/hari "
              f"({'+' if s['selisih'] >= 0 else ''}{rp(s['selisih'])})")

    # --- Demo pencatatan langsung (dibatalkan agar data tetap bersih) ---
    if args.demo:
        besok = (date.fromisoformat(tanggal_terakhir(con, w)) + timedelta(days=1)).isoformat()
        sebelum = con.execute("SELECT stok, hpp FROM produk WHERE warung_id=? AND produk=?", (w, top)).fetchone()
        catat_pembelian(con, w, besok, top, 20, int(sebelum[1]) + 300, komit=False)
        trx = catat_penjualan(con, w, besok, "07:00", [(top, 3), (top, 1)], komit=False)
        sesudah = con.execute("SELECT stok, hpp FROM produk WHERE warung_id=? AND produk=?", (w, top)).fetchone()
        print(f"\n=== DEMO CATAT TRANSAKSI ({top}) ===")
        print(f"Beli 20 pcs @ harga lebih mahal Rp300, jual 4 pcs (nota {trx})")
        print(f"Stok {sebelum[0]} -> {sesudah[0]} | HPP {rp(sebelum[1])} -> {rp(sesudah[1])}")
        try:
            catat_penjualan(con, w, besok, "08:00", [(top, 10_000)], komit=False)
        except ValueError as e:
            print(f"Validasi stok bekerja: {e}")
        con.rollback()
        print("(perubahan demo dibatalkan)")
    con.close()


if __name__ == "__main__":
    main()
