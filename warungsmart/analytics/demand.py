from .common import *
from .data import build_calendar

def _rolling(grid, col, shift, window, stat, min_periods):
    """Statistik rolling per seri, digeser `shift` hari (hanya memakai data <= t-shift)."""
    def f(x):
        return getattr(x.shift(shift).rolling(window, min_periods=min_periods), stat)()
    return grid.groupby(KEYS, sort=False)[col].transform(f)


def create_demand_dataset(df, stockout=None, horizon=FORECAST_HORIZON):
    banner("4. BUILDING DEMAND DATASET")
    first_date, last_date = df["tanggal"].min(), df["tanggal"].max()
    dates = pd.date_range(first_date, last_date + pd.Timedelta(days=horizon), freq="D")

    # ---- grid lengkap: setiap seri (warung x produk) x setiap tanggal ----
    series = df[KEYS + ["kategori"]].drop_duplicates(KEYS)
    grid = series.merge(pd.DataFrame({"tanggal": dates}), how="cross")
    obs = (df.groupby(KEYS + ["tanggal"], as_index=False)
             .agg(jumlah=("jumlah", "sum"), harga_jual=("harga_jual", "mean"),
                  harga_beli=("harga_beli", "mean")))
    grid = grid.merge(obs, on=KEYS + ["tanggal"], how="left")
    grid["jumlah"] = grid["jumlah"].fillna(0.0)          # hari tanpa penjualan = 0 (bukan baris hilang)

    if stockout is not None:
        so = (stockout.groupby(["warung_id", "tanggal", "produk"], as_index=False)["jumlah_hilang"]
                      .sum().rename(columns={"jumlah_hilang": "lost"}))
        grid = grid.merge(so, on=["warung_id", "tanggal", "produk"], how="left")
        grid["lost"] = grid["lost"].fillna(0.0)
    else:
        grid["lost"] = 0.0
    grid["demand"] = grid["jumlah"] + grid["lost"]

    grid = grid.sort_values(KEYS + ["tanggal"]).reset_index(drop=True)
    future_mask = grid["tanggal"] > last_date
    grid.loc[future_mask, ["jumlah", "lost", "demand"]] = np.nan

    # harga & HPP: teruskan nilai terakhir pada hari tanpa transaksi
    for c in ["harga_jual", "harga_beli"]:
        grid[c] = grid.groupby(KEYS, sort=False)[c].ffill()
        grid[c] = grid.groupby(KEYS, sort=False)[c].bfill()

    # ---- kalender ----
    grid = grid.merge(build_calendar(df, dates), on="tanggal", how="left")
    grid["day_of_week"] = grid["tanggal"].dt.dayofweek
    grid["month"] = grid["tanggal"].dt.month
    grid["day_of_month"] = grid["tanggal"].dt.day
    grid["week_of_year"] = grid["tanggal"].dt.isocalendar().week.astype(int)

    # ---- lag & rolling: semuanya digeser >= horizon ----
    H = horizon
    wk_lags = [7 * k for k in range(1, 9) if 7 * k >= H][:4]          # hari-yang-sama minggu lalu
    lags = sorted({H, H + 1, H + 2, H + 6, 14, 21, 28} | set(wk_lags))
    lags = [l for l in lags if l >= H]
    g = grid.groupby(KEYS, sort=False)["demand"]
    for l in lags:
        grid[f"lag_{l}"] = g.shift(l)
    grid["same_dow_mean"] = grid[[f"lag_{l}" for l in wk_lags]].mean(axis=1)
    for w in (7, 14, 28):
        grid[f"rmean_{w}"] = _rolling(grid, "demand", H, w, "mean", max(3, w // 2))
    grid["rstd_7"] = _rolling(grid, "demand", H, 7, "std", 4)
    grid["rstd_28"] = _rolling(grid, "demand", H, 28, "std", 14)
    grid["is_zero"] = (grid["demand"] == 0).astype(float).where(grid["demand"].notna())
    grid["zero_share_28"] = _rolling(grid, "is_zero", H, 28, "mean", 14)

    # ---- harga ----
    gp = grid.groupby(KEYS, sort=False)["harga_jual"]
    grid["margin_pct"] = (grid["harga_jual"] - grid["harga_beli"]) / grid["harga_jual"]
    grid["price_chg_1"] = grid["harga_jual"] / gp.shift(1) - 1
    grid["price_chg_7"] = grid["harga_jual"] / gp.shift(7) - 1
    grid["price_rel_28"] = grid["harga_jual"] / _rolling(grid, "harga_jual", 1, 28, "mean", 7)

    # ---- fitur khusus deteksi anomali (memakai hari kemarin) ----
    grid["rm28_1"] = _rolling(grid, "demand", 1, 28, "mean", 14)
    grid["rs28_1"] = _rolling(grid, "demand", 1, 28, "std", 14)
    scale = np.maximum.reduce([grid["rs28_1"].fillna(0).values,
                               np.sqrt(grid["rm28_1"].fillna(0).values),
                               np.full(len(grid), 0.5)])
    grid["z_qty"] = (grid["demand"] - grid["rm28_1"]) / scale

    # ---- total permintaan toko per hari (dipakai sebagai offset elastisitas) ----
    grid["shop_total"] = grid.groupby(["warung_id", "tanggal"])["demand"].transform("sum")

    # ---- daftar fitur model ----
    numeric = (["day_of_week", "month", "day_of_month", "week_of_year", "akhir_pekan",
                "libur_nasional", "gajian", "harga_jual", "margin_pct", "price_chg_7",
                "price_rel_28", "same_dow_mean", "rstd_7", "rstd_28", "zero_share_28"]
               + [f"lag_{l}" for l in lags] + [f"rmean_{w}" for w in (7, 14, 28)])
    if USE_WEATHER:
        numeric.append("hujan")
    META["numeric"] = numeric
    META["categories"] = {c: sorted(grid[c].dropna().unique()) for c in CAT_COLS + ["produk"]}

    warm = first_date + pd.Timedelta(days=28 + H)          # buang masa pemanasan lag/rolling
    daily = grid[(grid["tanggal"] <= last_date) & (grid["tanggal"] >= warm)].reset_index(drop=True)
    future = grid[grid["tanggal"] > last_date].reset_index(drop=True)

    zero_pct = 100 * (daily["jumlah"] == 0).mean()
    print(f"Seri (warung x produk) : {len(series):,}")
    print(f"Demand dataset         : {len(daily):,} baris ({zero_pct:.1f}% hari tanpa penjualan ikut dimodelkan)")
    print(f"Baris masa depan       : {len(future):,} ({horizon} hari)")
    print(f"Lag dipakai            : {lags} (semua >= horizon {H})")
    return daily, future


def make_X(data):
    X = data[META["numeric"]].copy()
    for c in CAT_COLS:
        X[c] = pd.Categorical(data[c], categories=META["categories"][c])
    prod = pd.Categorical(data["produk"], categories=META["categories"]["produk"])
    X["produk"] = prod if HAS_XGB else prod.codes
    return X
