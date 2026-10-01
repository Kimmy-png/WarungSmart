"""Cross-warung collaboration/complementarity derived from notebook cell 27."""
import os, warnings
import numpy as np
import pandas as pd
from scipy.spatial.distance import cosine
from itertools import combinations
warnings.filterwarnings("ignore")
def build_warung_feature_matrix():
    """Bangun vektor fitur per warung untuk menghitung similarity."""
    features = {}

    for wid in df_penjualan['warung_id'].unique():
        wdf = df_penjualan[df_penjualan['warung_id'] == wid]

        # --- Fitur komposisi kategori (share omzet) ---
        cat_share = wdf.groupby('kategori')['total_harga'].sum()
        cat_share = cat_share / cat_share.sum()

        # --- Fitur komposisi profil produk ---
        prod_share = wdf.groupby('produk')['jumlah'].sum()
        prod_share = prod_share / prod_share.sum()

        # --- Fitur numerik ---
        n_hari = wdf['tanggal'].nunique()
        features[wid] = {
            'omzet_per_hari': wdf['total_harga'].sum() / n_hari,
            'trx_per_hari': wdf['trx_id'].nunique() / n_hari,
            'basket_size': wdf['jumlah'].sum() / wdf['trx_id'].nunique(),
            'margin_rata2': wdf['total_profit'].sum() / max(wdf['total_harga'].sum(), 1),
            'n_sku_aktif': wdf['produk'].nunique(),
            'n_kategori': wdf['kategori'].nunique(),
            'cat_share': cat_share,
            'prod_share': prod_share,
        }

    return features


def compute_similarity_matrix(features, n_peers=2):
    """Hitung similarity matrix berbasis cosine pada komposisi kategori."""
    warungs = sorted(features.keys())
    n = len(warungs)

    # Ambil semua kategori yang ada
    all_cats = sorted(set(
        c for f in features.values() for c in f['cat_share'].index
    ))

    # Bangun matriks share kategori
    mat = np.zeros((n, len(all_cats)))
    for i, wid in enumerate(warungs):
        for j, cat in enumerate(all_cats):
            mat[i, j] = features[wid]['cat_share'].get(cat, 0)

    # Cosine similarity
    sim_matrix = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                sim_matrix[i, j] = 1.0
            else:
                sim_matrix[i, j] = 1 - cosine(mat[i], mat[j])

    sim_df = pd.DataFrame(sim_matrix, index=warungs, columns=warungs)

    # Tentukan peer terdekat untuk setiap warung
    peers = {}
    for wid in warungs:
        scores = sim_df.loc[wid].drop(wid).sort_values(ascending=False)
        peers[wid] = scores.head(n_peers).index.tolist()

    return sim_df, peers


def compute_kpi_table():
    """Hitung KPI utama per warung."""
    rows = []
    for wid in df_penjualan['warung_id'].unique():
        wdf = df_penjualan[df_penjualan['warung_id'] == wid]
        n_hari = wdf['tanggal'].nunique()

        omzet = wdf['total_harga'].sum()
        profit = wdf['total_profit'].sum()

        # Stockout rate
        if HAS_STOCKOUT:
            so = df_stockout[df_stockout['warung_id'] == wid]
            total_hilang = so['jumlah_hilang'].sum()
            total_demand = wdf['jumlah'].sum() + total_hilang
            so_rate = total_hilang / max(total_demand, 1)
        else:
            so_rate = np.nan
            total_hilang = 0

        rows.append({
            'warung_id': wid,
            'nama': df_warung[df_warung['warung_id'] == wid]['nama'].values[0]
                    if wid in df_warung['warung_id'].values else wid,
            'omzet_total': omzet,
            'omzet_per_hari': omzet / n_hari,
            'profit_total': profit,
            'profit_per_hari': profit / n_hari,
            'margin_pct': profit / max(omzet, 1),
            'trx_per_hari': wdf['trx_id'].nunique() / n_hari,
            'basket_size': wdf['jumlah'].sum() / max(wdf['trx_id'].nunique(), 1),
            'n_sku': wdf['produk'].nunique(),
            'stockout_rate': so_rate,
            'total_hilang': total_hilang,
        })

    return pd.DataFrame(rows)


def benchmark_vs_peers(kpi_df, peer_map):
    """Hitung rasio KPI warung vs peer median dan network median."""
    metrics = ['omzet_per_hari', 'margin_pct', 'trx_per_hari', 'basket_size', 'stockout_rate']
    results = []

    for _, row in kpi_df.iterrows():
        wid = row['warung_id']
        peers = peer_map.get(wid, [])

        # Peer median
        peer_kpi = kpi_df[kpi_df['warung_id'].isin(peers)]

        # Network median (exclude self)
        net_kpi = kpi_df[kpi_df['warung_id'] != wid]

        r = {'warung_id': wid, 'nama': row['nama']}
        for m in metrics:
            val = row[m]
            peer_med = peer_kpi[m].median() if len(peer_kpi) > 0 else np.nan
            net_med = net_kpi[m].median() if len(net_kpi) > 0 else np.nan

            # Untuk stockout, lebih rendah = lebih baik
            if m == 'stockout_rate':
                r[f'{m}_vs_peer'] = peer_med / max(val, 1e-9) if not np.isnan(peer_med) else np.nan
                r[f'{m}_vs_net'] = net_med / max(val, 1e-9) if not np.isnan(net_med) else np.nan
            else:
                r[f'{m}_vs_peer'] = val / max(peer_med, 1e-9) if not np.isnan(peer_med) else np.nan
                r[f'{m}_vs_net'] = val / max(net_med, 1e-9) if not np.isnan(net_med) else np.nan

        results.append(r)

    return pd.DataFrame(results)


def product_gap_analysis(min_omzet_peer=50000):
    """
    Identifikasi produk yang dijual peer tapi belum distok warung ini.
    min_omzet_peer: minimum omzet di peer agar dianggap 'layak' direkomendasikan.
    """
    results = []

    for wid in df_penjualan['warung_id'].unique():
        wdf = df_penjualan[df_penjualan['warung_id'] == wid]
        produk_saya = set(wdf['produk'].unique())
        peers = peer_map.get(wid, [])

        # Produk yang dijual peers
        peer_df = df_penjualan[df_penjualan['warung_id'].isin(peers)]
        peer_prod_stats = peer_df.groupby('produk').agg(
            omzet_peer=('total_harga', 'sum'),
            qty_peer=('jumlah', 'sum'),
            kategori=('kategori', 'first'),
            n_warung_peer=('warung_id', 'nunique'),
        ).reset_index()

        # Filter: belum dijual di warung ini & cukup laku di peer
        gap = peer_prod_stats[
            (~peer_prod_stats['produk'].isin(produk_saya)) &
            (peer_prod_stats['omzet_peer'] >= min_omzet_peer)
        ].copy()

        if len(gap) == 0:
            continue

        # Estimasi omzet harian jika warung ini juga menjual
        n_hari = peer_df['tanggal'].nunique()
        gap['estimasi_omzet_harian'] = gap['omzet_peer'] / max(n_hari, 1) / max(len(peers), 1)
        gap['estimasi_qty_harian'] = gap['qty_peer'] / max(n_hari, 1) / max(len(peers), 1)
        gap['warung_id'] = wid
        gap['n_produk_saya'] = len(produk_saya)

        results.append(gap.sort_values('estimasi_omzet_harian', ascending=False))

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


def peer_stock_recommendations(target_days=7):
    """
    Rekomendasikan stok berdasarkan perbandingan laju jual vs peer.
    Jika warung jual lebih lambat dari peer tapi punya produk yang sama,
    kemungkinan stok terlalu sedikit atau ada masalah display/lokasi.
    """
    results = []

    for wid in df_penjualan['warung_id'].unique():
        wdf = df_penjualan[df_penjualan['warung_id'] == wid]
        n_hari = wdf['tanggal'].nunique()
        peers = peer_map.get(wid, [])
        peer_df = df_penjualan[df_penjualan['warung_id'].isin(peers)]

        # Laju jual per produk di warung ini
        my_rates = wdf.groupby('produk').agg(
            qty_saya=('jumlah', 'sum'),
            stok_terakhir=('stok_akhir', 'last'),
            kategori=('kategori', 'first'),
        ).reset_index()
        my_rates['rate_saya'] = my_rates['qty_saya'] / max(n_hari, 1)

        # Laju jual per produk di peers
        peer_rates = peer_df.groupby('produk').agg(
            qty_peer=('jumlah', 'sum'),
        ).reset_index()
        n_hari_peer = peer_df['tanggal'].nunique()
        peer_rates['rate_peer'] = peer_rates['qty_peer'] / max(n_hari_peer, 1) / max(len(peers), 1)

        # Merge
        merged = my_rates.merge(peer_rates[['produk', 'rate_peer']], on='produk', how='inner')

        # Identifikasi produk dengan rate_saya << rate_peer (potensi understock)
        merged['ratio'] = merged['rate_saya'] / merged['rate_peer'].clip(lower=0.01)
        underperforming = merged[
            (merged['ratio'] < 0.5) &  # Jual kurang dari 50% laju peer
            (merged['rate_peer'] > 0.5)  # Peer cukup aktif jual
        ].copy()

        if len(underperforming) == 0:
            continue

        # Rekomendasi stok target
        underperforming['stok_target'] = np.ceil(underperforming['rate_peer'] * target_days)
        underperforming['saran_tambah'] = (underperforming['stok_target'] -
                                            underperforming['stok_terakhir']).clip(lower=0).astype(int)
        underperforming['warung_id'] = wid
        underperforming['hari_stok_sisa'] = (underperforming['stok_terakhir'] /
                                              underperforming['rate_saya'].clip(lower=0.01)).round(1)

        results.append(underperforming.sort_values('rate_peer', ascending=False))

    if results:
        return pd.concat(results, ignore_index=True)
    return pd.DataFrame()


def operating_hours_analysis():
    """
    Analisis pola jam penjualan per warung & bandingkan dengan peer.
    Identifikasi jam-jam di mana peer ramai tapi warung ini sepi.
    """
    results = []

    # Pola jam per warung
    hourly = df_penjualan.groupby(['warung_id', 'jam_int']).agg(
        omzet=('total_harga', 'sum'),
        qty=('jumlah', 'sum'),
        n_trx=('trx_id', 'nunique'),
    ).reset_index()

    # Normalisasi per warung (share dari total harian)
    daily_totals = hourly.groupby('warung_id')['omzet'].sum().reset_index()
    daily_totals.columns = ['warung_id', 'omzet_total']
    hourly = hourly.merge(daily_totals, on='warung_id')
    hourly['share_omzet'] = hourly['omzet'] / hourly['omzet_total'].clip(lower=1)

    # Untuk setiap warung, bandingkan dengan peer
    for wid in df_penjualan['warung_id'].unique():
        peers = peer_map.get(wid, [])
        my_hours = hourly[hourly['warung_id'] == wid][['jam_int', 'share_omzet']].set_index('jam_int')
        peer_hours = hourly[hourly['warung_id'].isin(peers)].groupby('jam_int')['share_omzet'].mean()

        # Jam di mana peer punya share tinggi tapi warung ini rendah
        all_hours = sorted(set(my_hours.index) | set(peer_hours.index))
        for h in all_hours:
            my_share = my_hours.loc[h, 'share_omzet'] if h in my_hours.index else 0
            peer_share = peer_hours.get(h, 0)

            if peer_share > 0.05 and my_share < peer_share * 0.5:
                results.append({
                    'warung_id': wid,
                    'jam': int(h),
                    'share_saya': my_share,
                    'share_peer': peer_share,
                    'gap': peer_share - my_share,
                    'rekomendasi': f"Peer dapat {peer_share:.1%} omzet di jam {int(h):02d}:00, "
                                   f"warung Anda hanya {my_share:.1%}. "
                                   f"Potensi tambahan: ~{gap:.1%} omzet."
                })

    return pd.DataFrame(results), hourly


def cross_warung_anomaly(window=7):
    """
    Deteksi anomali spesifik warung vs tren jaringan.
    Jika satu warung turun tapi peer naik → masalah internal.
    Jika semua turun → tren pasar/musiman.
    """
    # Hitung omzet harian per warung
    daily = df_penjualan.groupby(['warung_id', 'tanggal'])['total_harga'].sum().reset_index()
    daily.columns = ['warung_id', 'tanggal', 'omzet']

    last_date = daily['tanggal'].max()
    recent_start = last_date - pd.Timedelta(days=window)
    prev_start = last_date - pd.Timedelta(days=2 * window)

    results = []

    for wid in df_penjualan['warung_id'].unique():
        wdf = daily[daily['warung_id'] == wid]

        recent = wdf[wdf['tanggal'] > recent_start]['omzet'].sum()
        prev = wdf[(wdf['tanggal'] > prev_start) & (wdf['tanggal'] <= recent_start)]['omzet'].sum()

        growth_self = (recent - prev) / max(prev, 1)

        # Growth peers
        peers = peer_map.get(wid, [])
        peer_daily = daily[daily['warung_id'].isin(peers)]
        peer_recent = peer_daily[peer_daily['tanggal'] > recent_start]['omzet'].sum()
        peer_prev = peer_daily[(peer_daily['tanggal'] > prev_start) &
                               (peer_daily['tanggal'] <= recent_start)]['omzet'].sum()
        growth_peer = (peer_recent - peer_prev) / max(peer_prev, 1)

        # Network growth (all warungs except self)
        net_daily = daily[daily['warung_id'] != wid]
        net_recent = net_daily[net_daily['tanggal'] > recent_start]['omzet'].sum()
        net_prev = net_daily[(net_daily['tanggal'] > prev_start) &
                             (net_daily['tanggal'] <= recent_start)]['omzet'].sum()
        growth_net = (net_recent - net_prev) / max(net_prev, 1)

        # Diagnosis
        delta_vs_peer = growth_self - growth_peer

        if growth_self < -0.05 and growth_peer > 0:
            diagnosis = "MASALAH_SPESIFIK_WARUNG"
            severity = "HIGH"
        elif growth_self < -0.05 and growth_peer < -0.05:
            diagnosis = "TREN_PASAR_MENURUN"
            severity = "LOW"
        elif growth_self > 0.05 and growth_peer <= 0:
            diagnosis = "KINERJA_BAIK_SPESIFIK"
            severity = "INFO"
        elif growth_self > 0.05 and growth_peer > 0.05:
            diagnosis = "TREN_PASAR_NAIK"
            severity = "INFO"
        else:
            diagnosis = "NORMAL"
            severity = "LOW"

        results.append({
            'warung_id': wid,
            'growth_self': growth_self,
            'growth_peer': growth_peer,
            'growth_network': growth_net,
            'delta_vs_peer': delta_vs_peer,
            'diagnosis': diagnosis,
            'severity': severity,
        })

    return pd.DataFrame(results)


def compute_health_score(kpi_df, peer_map):
    """
    Hitung skor kesehatan warung 0-100 berdasarkan perbandingan vs peer.
    Komponen:
      - Omzet (30%)
      - Margin (20%)
      - Frekuensi transaksi (15%)
      - Basket size (15%)
      - Stockout rate (20%) - lebih rendah = lebih baik
    """

    def ratio_score(value, reference, higher_is_better=True):
        """Konversi rasio ke skor 0-100. Rasio 1.0 = 50."""
        if np.isnan(value) or np.isnan(reference) or reference == 0:
            return 50
        ratio = value / reference
        if not higher_is_better:
            ratio = 1 / max(ratio, 0.01)
        # Map: ratio 0.5 → 0, ratio 1.0 → 50, ratio 1.5+ → 100
        score = np.clip((ratio - 0.5) * 100, 0, 100)
        return int(round(score))

    results = []

    for _, row in kpi_df.iterrows():
        wid = row['warung_id']
        peers = peer_map.get(wid, [])
        peer_kpi = kpi_df[kpi_df['warung_id'].isin(peers)]

        # Referensi = median peer
        ref = {
            'omzet_per_hari': peer_kpi['omzet_per_hari'].median() if len(peer_kpi) > 0 else np.nan,
            'margin_pct': peer_kpi['margin_pct'].median() if len(peer_kpi) > 0 else np.nan,
            'trx_per_hari': peer_kpi['trx_per_hari'].median() if len(peer_kpi) > 0 else np.nan,
            'basket_size': peer_kpi['basket_size'].median() if len(peer_kpi) > 0 else np.nan,
            'stockout_rate': peer_kpi['stockout_rate'].median() if len(peer_kpi) > 0 else np.nan,
        }

        scores = {
            'omzet': ratio_score(row['omzet_per_hari'], ref['omzet_per_hari']),
            'margin': ratio_score(row['margin_pct'], ref['margin_pct']),
            'frekuensi': ratio_score(row['trx_per_hari'], ref['trx_per_hari']),
            'basket': ratio_score(row['basket_size'], ref['basket_size']),
            'stockout': ratio_score(row['stockout_rate'], ref['stockout_rate'], higher_is_better=False),
        }

        # Weighted total
        weights = {'omzet': 0.30, 'margin': 0.20, 'frekuensi': 0.15,
                   'basket': 0.15, 'stockout': 0.20}
        total = sum(scores[k] * w for k, w in weights.items())

        results.append({
            'warung_id': wid,
            'nama': row['nama'],
            'skor_total': int(round(total)),
            **scores,
            'grade': 'A' if total >= 80 else 'B' if total >= 60 else 'C' if total >= 40 else 'D',
        })

    return pd.DataFrame(results)


def referral_opportunities():
    """
    Identifikasi peluang referral antar-warung:
    - Produk yang sering stockout di warung A tapi tersedia di warung B
    - Produk komplementer yang bisa di-bundle lintas warung
    """
    if not HAS_STOCKOUT:
        print("Data stockout tidak tersedia. Skipping referral analysis.")
        return pd.DataFrame(), pd.DataFrame()

    # --- Peluang Referral Stockout ---
    # Produk yang sering stockout di warung A
    so_by_warung_prod = df_stockout.groupby(['warung_id', 'produk']).agg(
        total_hilang=('jumlah_hilang', 'sum'),
        n_kejadian=('jumlah_hilang', 'count'),
    ).reset_index()

    # Produk yang tersedia (pernah dijual) di warung lain
    prod_available = df_penjualan.groupby(['warung_id', 'produk']).size().reset_index(name='n_trx')
    prod_available_set = set(zip(prod_available['warung_id'], prod_available['produk']))

    referrals = []
    for _, row in so_by_warung_prod.iterrows():
        wid = row['warung_id']
        prod = row['produk']

        # Cari warung lain yang jual produk ini
        for other_wid in df_penjualan['warung_id'].unique():
            if other_wid == wid:
                continue
            if (other_wid, prod) in prod_available_set:
                referrals.append({
                    'warung_stockout': wid,
                    'produk': prod,
                    'total_hilang': row['total_hilang'],
                    'n_kejadian': row['n_kejadian'],
                    'warung_referral': other_wid,
                    'tipe': 'REFERRAL_STOCKOUT',
                })

    referral_df = pd.DataFrame(referrals)

    # --- Complementarity Analysis ---
    # Produk yang sering dibeli bersamaan di satu warung tapi terpisah di warung lain
    # (simplified: kategori yang sering co-occur dalam transaksi)
    trx_items = df_penjualan.groupby(['warung_id', 'trx_id'])['kategori'].apply(set).reset_index()

    # Co-occurrence per warung
    complementarity = []
    for wid in df_penjualan['warung_id'].unique():
        wtrx = trx_items[trx_items['warung_id'] == wid]
        cat_sets = wtrx['kategori'].values

        # Hitung co-occurrence
        cooccur = {}
        for s in cat_sets:
            for pair in combinations(sorted(s), 2):
                cooccur[pair] = cooccur.get(pair, 0) + 1

        # Top pairs
        top_pairs = sorted(cooccur.items(), key=lambda x: -x[1])[:5]
        for (cat1, cat2), count in top_pairs:
            complementarity.append({
                'warung_id': wid,
                'kategori_1': cat1,
                'kategori_2': cat2,
                'co_occurrence': count,
                'tipe': 'COMPLEMENTARY_BUNDLE',
            })

    comp_df = pd.DataFrame(complementarity)

    return referral_df, comp_df
