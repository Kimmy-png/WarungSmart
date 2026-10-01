from .common import *

def load_data(path):
    banner("1. LOADING DATA")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"File data tidak ditemukan: {path}\n"
            "Set DATA_PATH atau environment variable RETAIL_DATA_PATH.")
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Kolom wajib tidak ada: {missing}")
    if "fase_akademik" not in df.columns:
        print("PERINGATAN: kolom 'fase_akademik' tidak ada -> diisi 'BIASA'.")
        df["fase_akademik"] = "BIASA"
    print(f"Rows    : {len(df):,}")
    print(f"Columns : {len(df.columns)}")
    return df


def load_stockout(path):
    if not CORRECT_STOCKOUT or not os.path.exists(path):
        print("Koreksi stockout: TIDAK dipakai (file tidak ada / dimatikan).")
        return None
    so = pd.read_csv(path)
    so["tanggal"] = pd.to_datetime(so["tanggal"], errors="coerce")
    print(f"Koreksi stockout: dipakai ({len(so):,} kejadian)")
    return so


def clean_data(df):
    banner("2. CLEANING DATA")
    df = df.copy()
    df["tanggal"] = pd.to_datetime(df["tanggal"], errors="coerce")

    num_cols = ["jumlah", "harga_jual", "harga_beli", "stok_akhir", "populasi", "frac_sku",
                "sku_aktif", "mult_harga", "hujan", "akhir_pekan", "libur_nasional", "gajian"]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    before = len(df)
    df = df.dropna(subset=["tanggal", "produk", "jumlah", "harga_jual", "harga_beli"])
    df = df[(df["jumlah"] > 0) & (df["harga_jual"] > 0) & (df["harga_beli"] > 0)]
    dup = df.duplicated().sum()
    df = df.drop_duplicates()
    print(f"Baris tidak valid dibuang : {before - len(df) - dup:,}")
    print(f"Baris duplikat dibuang    : {dup:,}")

    for c in ["hujan", "akhir_pekan", "libur_nasional", "gajian"]:
        df[c] = df[c].fillna(0).astype(int)
    df["fase_akademik"] = df["fase_akademik"].fillna("BIASA")

    # satu produk harus punya satu kategori
    n_kat = df.groupby("produk")["kategori"].nunique()
    if (n_kat > 1).any():
        raise ValueError(f"Produk dengan >1 kategori: {list(n_kat[n_kat > 1].index[:5])}")

    df = df.sort_values(["warung_id", "produk", "tanggal"]).reset_index(drop=True)

    df["revenue"] = df["jumlah"] * df["harga_jual"]
    df["profit"] = df["jumlah"] * (df["harga_jual"] - df["harga_beli"])
    df["margin"] = (df["harga_jual"] - df["harga_beli"]) / df["harga_jual"]
    df["year"] = df["tanggal"].dt.year
    df["month"] = df["tanggal"].dt.month
    df["day_of_week"] = df["tanggal"].dt.dayofweek

    rugi = (df["harga_jual"] < df["harga_beli"]).sum()
    print(f"Baris terjual di bawah HPP: {rugi:,} ({100 * rugi / len(df):.2f}%)")
    print(f"Data setelah cleaning     : {df.shape}")
    return df


def run_eda(df):
    banner("3. EXPLORATORY DATA ANALYSIS")

    print("\nTop 20 produk (unit):")
    print(df.groupby("produk")["jumlah"].sum().sort_values(ascending=False).head(20))
    print("\nKategori (unit):")
    print(df.groupby("kategori")["jumlah"].sum().sort_values(ascending=False))

    per_warung = df.groupby("warung_id").agg(
        transaksi=("trx_id", "nunique"), omzet=("revenue", "sum"), laba=("profit", "sum"))
    per_warung["margin_%"] = 100 * per_warung["laba"] / per_warung["omzet"]
    print("\nRingkasan per warung:")
    print(per_warung.round(1))
    print(f"\nTotal omzet : Rp {df['revenue'].sum():,.0f}")
    print(f"Total laba  : Rp {df['profit'].sum():,.0f}")

    daily = (df.groupby("tanggal")
               .agg(quantity=("jumlah", "sum"), revenue=("revenue", "sum"),
                    profit=("profit", "sum"))
               .reset_index())
    plt.figure(figsize=(14, 5))
    plt.plot(daily["tanggal"], daily["quantity"])
    plt.title("Daily Retail Quantity")
    plt.xlabel("Date")
    plt.ylabel("Quantity")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/daily_sales.png")
    plt.close()
    return daily


def build_calendar(df, dates):
    """Kalender per tanggal. Tanggal masa depan: akhir pekan & gajian dihitung dari aturan,
    libur nasional = 0 (tidak diketahui), fase akademik = fase terakhir yang diketahui."""
    idx = pd.DatetimeIndex(dates)
    obs = df.groupby("tanggal")[["hujan", "akhir_pekan", "libur_nasional", "gajian"]].first()
    obs_fase = df.groupby("tanggal")["fase_akademik"].first()
    cal = pd.DataFrame(index=idx)
    cal["akhir_pekan"] = obs["akhir_pekan"].reindex(idx).fillna(pd.Series(idx.dayofweek >= 5, index=idx).astype(int))
    cal["gajian"] = obs["gajian"].reindex(idx).fillna(pd.Series(idx.day.isin(list(GAJIAN_DAYS)), index=idx).astype(int))
    cal["libur_nasional"] = obs["libur_nasional"].reindex(idx).fillna(0)
    cal["hujan"] = obs["hujan"].reindex(idx).fillna(0)
    cal["fase_akademik"] = obs_fase.reindex(idx).ffill().bfill().fillna("BIASA")
    return cal.rename_axis("tanggal").reset_index()
