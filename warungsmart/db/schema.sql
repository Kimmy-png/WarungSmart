-- Skema SQLite WarungSmart.
-- `transaksi.jam` NULLABLE: pencatatan harian mengisi NULL. Jika kelak ada data
-- per jam, tidak perlu migrasi; cukup aktifkan HOURLY_FEATURES_ENABLED.
CREATE TABLE IF NOT EXISTS warung (
    id      INTEGER PRIMARY KEY,
    nama    TEXT NOT NULL UNIQUE,
    pemilik TEXT
);

CREATE TABLE IF NOT EXISTS produk (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    warung_id  INTEGER NOT NULL REFERENCES warung(id),
    nama       TEXT NOT NULL,
    kategori   TEXT NOT NULL,
    harga_beli REAL NOT NULL CHECK (harga_beli >= 0),
    harga_jual REAL NOT NULL CHECK (harga_jual >= 0),
    stok       INTEGER NOT NULL DEFAULT 0,
    stok_min   INTEGER NOT NULL DEFAULT 5,
    aktif      INTEGER NOT NULL DEFAULT 1,
    UNIQUE (warung_id, nama)
);

CREATE TABLE IF NOT EXISTS transaksi (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    warung_id  INTEGER NOT NULL REFERENCES warung(id),
    produk_id  INTEGER NOT NULL REFERENCES produk(id),
    tanggal    TEXT NOT NULL,                       -- ISO yyyy-mm-dd
    jam        INTEGER CHECK (jam IS NULL OR jam BETWEEN 0 AND 23),
    qty        INTEGER NOT NULL CHECK (qty > 0),
    total      REAL NOT NULL,                       -- qty * harga_jual saat dicatat
    hpp        REAL NOT NULL,                       -- qty * harga_beli saat dicatat
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_trx_warung_tgl ON transaksi (warung_id, tanggal);
CREATE INDEX IF NOT EXISTS idx_trx_produk     ON transaksi (produk_id);
