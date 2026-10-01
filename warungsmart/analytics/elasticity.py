from .common import *

def fe_poisson_slope(y, x, offset, fe, cluster):
    """
    Poisson (PPML) dengan SATU regressor x, fixed effect grup `fe`, dan offset log-trafik:
        E[y] = exp(alpha_grup + beta * x + offset)
    Fixed effect di-'partial out' tiap iterasi IRLS, jadi cepat walau grupnya ratusan.
    Kembalian: beta, SE (cluster-robust), SE (model), jumlah baris terpakai.
    """
    y, x, offset = np.asarray(y, float), np.asarray(x, float), np.asarray(offset, float)
    fe = pd.factorize(np.asarray(fe))[0]
    tot = np.bincount(fe, weights=y)
    keep = tot[fe] > 0                                   # grup tanpa penjualan tidak informatif
    y, x, offset, fe = y[keep], x[keep], offset[keep], fe[keep]
    cluster = np.asarray(cluster)[keep]
    fe = pd.factorize(fe)[0]
    ng = fe.max() + 1
    cl = pd.factorize(cluster)[0]
    n_cl = cl.max() + 1

    alpha = np.log(np.bincount(fe, weights=y) / np.bincount(fe, weights=np.exp(offset)))
    beta = 0.0
    for _ in range(200):
        eta = np.clip(alpha[fe] + beta * x + offset, -30, 20)
        mu = np.exp(eta)
        z = eta - offset + (y - mu) / mu
        sw = np.bincount(fe, weights=mu)
        xm = np.bincount(fe, weights=mu * x) / sw
        zm = np.bincount(fe, weights=mu * z) / sw
        xt = x - xm[fe]
        sxx = (mu * xt * xt).sum()
        beta_new = (mu * xt * (z - zm[fe])).sum() / sxx
        alpha = zm - beta_new * xm
        done = abs(beta_new - beta) < 1e-9
        beta = beta_new
        if done:
            break

    eta = np.clip(alpha[fe] + beta * x + offset, -30, 20)
    mu = np.exp(eta)
    sw = np.bincount(fe, weights=mu)
    xt = x - (np.bincount(fe, weights=mu * x) / sw)[fe]
    sxx = (mu * xt * xt).sum()
    resid = y - mu
    phi = (resid ** 2 / mu).sum() / max(len(y) - ng - 1, 1)            # dispersi quasi-Poisson
    se_model = np.sqrt(phi / sxx)
    S = np.bincount(cl, weights=xt * resid, minlength=n_cl)
    se_cluster = np.sqrt((S ** 2).sum() * n_cl / max(n_cl - 1, 1)) / sxx
    return beta, se_cluster, se_model, int(len(y))


def _elasticity_row(beta, se, n_obs, n_units, price_sd, extra):
    z = beta / se if se > 0 else np.nan
    p = 2 * (1 - stats.norm.cdf(abs(z))) if np.isfinite(z) else np.nan
    return {**extra, "n_observations": n_obs, "units": n_units, "price_sd": price_sd,
            "elasticity": beta, "se": se, "ci_low": beta - 1.96 * se, "ci_high": beta + 1.96 * se,
            "p_value": p, "reliable": bool(np.isfinite(p) and p < 0.05 and beta < 0)}


def estimate_price_elasticity(daily):
    """
    Elastisitas = d log(pangsa permintaan produk di toko) / d log(harga relatif).
      * grid lengkap (hari nol ikut), Poisson -> tidak ada bias seleksi dari log(0)
      * offset log(total permintaan toko-hari) -> trafik, cuaca, kalender ikut terkontrol
      * fixed effect per seri warung-produk
      * harga relatif = harga produk dibanding indeks harga toko (membuang inflasi umum)
    """
    banner("7. PRICE ELASTICITY")
    d = daily[["warung_id", "produk", "kategori", "tanggal", "demand", "harga_jual", "shop_total"]].copy()
    d = d[(d["harga_jual"] > 0) & (d["shop_total"] > 0)]
    d["series"] = d["warung_id"] + "|" + d["produk"]
    d["lp"] = np.log(d["harga_jual"])
    d["lp_dm"] = d["lp"] - d.groupby("series")["lp"].transform("mean")
    d["rel_price"] = d["lp_dm"] - d.groupby(["warung_id", "tanggal"])["lp_dm"].transform("mean")
    d["offset"] = np.log(d["shop_total"])
    d["week"] = (d["tanggal"] - d["tanggal"].min()).dt.days // 7

    # ---- level kategori (paling stabil): cluster per seri ----
    cat_rows = []
    for kat, g in d.groupby("kategori"):
        if g["demand"].sum() < 200:
            continue
        b, se, _, n = fe_poisson_slope(g["demand"], g["rel_price"], g["offset"], g["series"], g["series"])
        cat_rows.append(_elasticity_row(b, se, n, g["demand"].sum(), g["rel_price"].std(),
                                        {"kategori": kat, "n_seri": g["series"].nunique()}))
    cat_df = pd.DataFrame(cat_rows).sort_values("elasticity")
    cat_df.to_csv(f"{OUTPUT_DIR}/elasticity_category.csv", index=False)
    print("\nElastisitas per kategori (dengan 95% CI):")
    print(cat_df[["kategori", "elasticity", "ci_low", "ci_high", "p_value", "reliable"]].round(3).to_string(index=False))

    # ---- level produk (lebih berisik): cluster per minggu ----
    rows = []
    for produk, g in d.groupby("produk"):
        if len(g) < 300 or g["demand"].sum() < 100 or g["rel_price"].std() < 0.005:
            continue
        b, se, _, n = fe_poisson_slope(g["demand"], g["rel_price"], g["offset"], g["warung_id"], g["week"])
        rows.append(_elasticity_row(b, se, n, g["demand"].sum(), g["rel_price"].std(),
                                    {"produk": produk, "kategori": g["kategori"].iloc[0]}))
    elasticity_df = pd.DataFrame(rows)
    if len(elasticity_df):
        elasticity_df = elasticity_df.sort_values("elasticity")
    elasticity_df.to_csv(f"{OUTPUT_DIR}/elasticity.csv", index=False)
    n_rel = int(elasticity_df["reliable"].sum()) if len(elasticity_df) else 0
    print(f"\nProduk dianalisis: {len(elasticity_df)} | signifikan & bertanda negatif: {n_rel}")
    if n_rel:
        print("\nProduk paling sensitif harga (hanya yang signifikan):")
        print(elasticity_df[elasticity_df["reliable"]]
              [["produk", "elasticity", "ci_low", "ci_high", "p_value"]].head(15).round(3).to_string(index=False))
    print("\nCATATAN: variasi harga di data ini kecil (SD harga relatif ~1-3%), sehingga CI produk lebar.")
    print("Gunakan angka level kategori untuk keputusan; uji harga nyata (A/B) untuk produk penting.")
    return elasticity_df, cat_df
