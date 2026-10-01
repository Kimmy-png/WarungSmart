"""Cross-warung peer intelligence derived from notebook cell 26."""
import os, json
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
N_PEERS=2
def build_similarity(df_penjualan):
    """Similarity antar-warung berbasis komposisi omzet per kategori."""
    pivot = df_penjualan.pivot_table(
        index="warung_id", columns="kategori",
        values="total_harga", aggfunc="sum", fill_value=0)
    share = pivot.div(pivot.sum(axis=1), axis=0)          # profil omzet (share)
    sim = pd.DataFrame(cosine_similarity(share.values),
                       index=share.index, columns=share.index)
    return sim


def get_peers(wid, sim, k=N_PEERS):
    """K warung paling mirip (tidak termasuk diri sendiri)."""
    return sim.loc[wid].drop(wid).sort_values(ascending=False).head(k)


def warung_kpi(df_penjualan, df_warung, df_stockout):
    rows = []
    for _, w in df_warung.iterrows():
        wid = w["warung_id"]
        pj  = df_penjualan[df_penjualan["warung_id"] == wid]
        so  = df_stockout[df_stockout["warung_id"] == wid] if df_stockout is not None else pd.DataFrame()

        omzet   = pj["total_harga"].sum()
        n_hari  = pj["tanggal"].nunique()
        n_trx   = pj["trx_id"].nunique()
        cogs    = (pj["jumlah"] * pj["harga_beli"]).sum()
        margin  = (omzet - cogs) / omzet if omzet > 0 else 0
        terjual = pj["jumlah"].sum()
        hilang  = so["jumlah_hilang"].sum() if len(so) else 0
        demand  = terjual + hilang
        so_rate = hilang / demand if demand > 0 else 0

        rows.append({
            "warung_id": wid, "nama": w["nama"],
            "omzet_per_hari": omzet / max(n_hari, 1),
            "trx_per_hari": n_trx / max(n_hari, 1),
            "basket_size": terjual / max(n_trx, 1),
            "margin": margin,
            "stockout_rate": so_rate,
            "sku_aktif": pj["produk"].nunique(),
            "n_hari": n_hari,
        })
    return pd.DataFrame(rows).set_index("warung_id")


def benchmark_report(kpi, sim):
    """Bandingkan tiap warung dengan peer terdekat & median jaringan."""
    out = []
    for wid in kpi.index:
        peers = get_peers(wid, sim).index
        peer_med = kpi.loc[peers].median(numeric_only=True)
        net_med  = kpi.drop(wid).median(numeric_only=True)
        row = {"warung_id": wid, "peer": list(peers)}
        for m in ["omzet_per_hari", "margin", "stockout_rate", "basket_size"]:
            row[f"{m}_vs_peer"] = (kpi.at[wid, m] / peer_med[m]) if peer_med[m] else np.nan
            row[f"{m}_vs_jaringan"] = (kpi.at[wid, m] / net_med[m]) if net_med[m] else np.nan
        out.append(row)
    return pd.DataFrame(out).set_index("warung_id")


def product_gap(df_penjualan, sim, min_omzet_peer=100_000):
    """Produk yang laku di peer tapi belum distok warung ini."""
    hasil = []
    omz = df_penjualan.groupby(["warung_id", "produk"]).agg(
        omzet=("total_harga", "sum"), qty=("jumlah", "sum"),
        kategori=("kategori", "first")).reset_index()

    for wid in df_penjualan["warung_id"].unique():
        punya_saya = set(df_penjualan.loc[df_penjualan["warung_id"] == wid, "produk"])
        peers = get_peers(wid, sim).index
        kandidat = omz[omz["warung_id"].isin(peers)]

        for prod, g in kandidat.groupby("produk"):
            if prod in punya_saya:
                continue
            omzet_peer = g["omzet"].sum()
            if omzet_peer < min_omzet_peer:
                continue
            # estimasi potensi: rata-rata omzet peer per warung
            hasil.append({
                "warung_id": wid, "produk": prod,
                "kategori": g["kategori"].iloc[0],
                "omzet_peer_total": omzet_peer,
                "estimasi_omzet_harian": omzet_peer / len(peers) / df_penjualan["tanggal"].nunique(),
                "qty_peer_total": int(g["qty"].sum()),
            })
    gap = pd.DataFrame(hasil)
    if len(gap):
        gap = gap.sort_values(["warung_id", "estimasi_omzet_harian"],
                              ascending=[True, False])
    return gap


def stock_recommendation(df_penjualan, sim, target_days=7):
    """
    Bandingkan 'hari stok' warung vs peer untuk produk yang sama.
    Jika warung pegang stok lebih tipis dari peer padahal laku, naikkan.
    """
    hasil = []
    for wid in df_penjualan["warung_id"].unique():
        pj_saya  = df_penjualan[df_penjualan["warung_id"] == wid]
        peers    = get_peers(wid, sim).index
        pj_peer  = df_penjualan[df_penjualan["warung_id"].isin(peers)]
        n_hari   = pj_saya["tanggal"].nunique()

        stok_terakhir = (pj_saya.sort_values("tanggal")
                         .groupby("produk")["stok_akhir"].last())

        for prod in pj_saya["produk"].unique():
            d_saya = pj_saya.loc[pj_saya["produk"] == prod, "jumlah"].sum() / max(n_hari, 1)
            d_peer = pj_peer.loc[pj_peer["produk"] == prod, "jumlah"].sum() / max(n_hari, 1) / max(len(peers), 1)
            if d_peer <= 0:
                continue
            stok = float(stok_terakhir.get(prod, 0))
            hari_stok_saya = stok / d_saya if d_saya > 0 else np.inf
            hari_stok_peer = (stok / d_peer) if d_peer > 0 else np.inf
            target = np.ceil(d_peer * target_days)
            if hari_stok_peer < 3 and d_saya >= d_peer * 0.7:
                # stok menipis relatif terhadap laju permintaan peer
                hasil.append({
                    "warung_id": wid, "produk": prod,
                    "stok_sekarang": int(stok),
                    "laju_jual_saya": round(d_saya, 2),
                    "laju_jual_peer": round(d_peer, 2),
                    "hari_stok_sisa": round(min(hari_stok_saya, 999), 1),
                    "stok_target_disarankan": int(target),
                    "saran_tambah": int(max(0, target - stok)),
                })
    rec = pd.DataFrame(hasil)
    if len(rec):
        rec = rec.sort_values(["warung_id", "hari_stok_sisa"])
    return rec


def operating_hours(df_penjualan, sim):
    """Cari jam ramai di peer yang tidak tercakup oleh warung ini."""
    pola = (df_penjualan.groupby(["warung_id", "jam_int"])["total_harga"]
            .sum().reset_index())
    hasil = []
    for wid in df_penjualan["warung_id"].unique():
        peers = get_peers(wid, sim).index
        jam_saya = set(pola.loc[pola["warung_id"] == wid, "jam_int"])
        peer_pola = pola[pola["warung_id"].isin(peers)]
        total_peer = peer_pola["total_harga"].sum()
        for jam, g in peer_pola.groupby("jam_int"):
            share = g["total_harga"].sum() / total_peer if total_peer else 0
            status = "TERBUKA" if jam in jam_saya else "TUTUP"
            hasil.append({"warung_id": wid, "jam": int(jam),
                          "share_omzet_peer": share, "status_saya": status})
    jam_df = pd.DataFrame(hasil)

    # ringkas peluang yang hilang
    missed = jam_df[(jam_df["status_saya"] == "TUTUP") &
                    (jam_df["share_omzet_peer"] >= 0.05)]
    missed = missed.sort_values(["warung_id", "share_omzet_peer"],
                                ascending=[True, False])
    return jam_df, missed


def cross_warung_anomaly(df_penjualan, sim, window=7):
    """Jika warung turun tapi peer naik -> kemungkinan masalah internal."""
    daily = (df_penjualan.groupby(["warung_id", "tanggal"])["total_harga"]
             .sum().reset_index())
    last = daily["tanggal"].max()
    rec  = daily[daily["tanggal"] > last - pd.Timedelta(days=window)]
    prev = daily[(daily["tanggal"] <= last - pd.Timedelta(days=window)) &
                 (daily["tanggal"] > last - pd.Timedelta(days=2 * window))]
    g_rec  = rec.groupby("warung_id")["total_harga"].sum()
    g_prev = prev.groupby("warung_id")["total_harga"].sum()
    growth = ((g_rec - g_prev) / g_prev.replace(0, np.nan)).dropna()

    hasil = []
    for wid in growth.index:
        peers = get_peers(wid, sim).index
        peer_growth = growth.reindex(peers).mean()
        delta = growth[wid] - peer_growth
        if growth[wid] < -0.05 and peer_growth > 0:
            jenis = "MASALAH_SPESIFIK_WARUNG"
        elif growth[wid] < -0.05 and peer_growth < -0.05:
            jenis = "TREN_PASAR_MENURUN"
        elif growth[wid] > 0.05 and peer_growth > 0.05:
            jenis = "TREN_PASAR_NAIK"
        elif growth[wid] > 0.05 and peer_growth <= 0:
            jenis = "KINERJA_BAIK_SPESIFIK"
        else:
            jenis = "NORMAL"
        hasil.append({"warung_id": wid,
                      "growth_7hari": round(growth[wid], 3),
                      "growth_peer": round(peer_growth, 3),
                      "selisih": round(delta, 3),
                      "diagnosis": jenis})
    return pd.DataFrame(hasil).set_index("warung_id")


def ratio_score(nilai, ref, arah=1):
    """Map rasio nilai/referensi ke skor 0-100 (rasio 1.0 -> 50)."""
    if ref is None or ref == 0 or pd.isna(ref):
        return 50
    r = nilai / ref
    if arah == -1:
        r = 1 / r if r > 0 else 2.0
    return int(np.clip((r - 0.5) * 100, 0, 100))


def health_score(kpi, sim):
    rows = []
    for wid in kpi.index:
        peers = get_peers(wid, sim).index
        pm = kpi.loc[peers].median(numeric_only=True)
        skor = {
            "omzet":       ratio_score(kpi.at[wid, "omzet_per_hari"], pm["omzet_per_hari"]),
            "margin":      ratio_score(kpi.at[wid, "margin"], pm["margin"]),
            "stockout":    ratio_score(kpi.at[wid, "stockout_rate"], pm["stockout_rate"], arah=-1),
            "basket":      ratio_score(kpi.at[wid, "basket_size"], pm["basket_size"]),
        }
        bobot = {"omzet": 0.35, "margin": 0.25, "stockout": 0.25, "basket": 0.15}
        total = sum(skor[k] * w for k, w in bobot.items())
        rows.append({"warung_id": wid, "skor_total": int(round(total)), **skor})
    return pd.DataFrame(rows).set_index("warung_id")
