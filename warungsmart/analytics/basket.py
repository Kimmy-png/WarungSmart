from .common import *

def _pair_rules(df, item_col):
    """Aturan asosiasi A -> B (pasangan) lewat perkalian matriks sparse. Tanpa mlxtend, hemat memori."""
    pairs = df[["trx_id", item_col]].drop_duplicates()
    t_code, _ = pd.factorize(pairs["trx_id"])
    i_code, items = pd.factorize(pairs[item_col])
    M = sparse.csr_matrix((np.ones(len(pairs), dtype=np.int32), (t_code, i_code)))
    M = M[np.asarray(M.sum(axis=1)).ravel() >= 2]          # basket 1 item tidak memuat asosiasi
    n = M.shape[0]
    item_cnt = np.asarray(M.sum(axis=0)).ravel()
    co = (M.T @ M).tocoo()
    m = (co.row != co.col) & (co.data >= MIN_PAIR_COUNT) & (co.data / n >= MIN_SUPPORT)
    a, b, c = co.row[m], co.col[m], co.data[m]
    support = c / n
    confidence = c / item_cnt[a]
    lift = confidence / (item_cnt[b] / n)
    rules = pd.DataFrame({
        "antecedents": items[a], "consequents": items[b], "pair_count": c,
        "support": support, "confidence": confidence, "lift": lift,
        "leverage": support - (item_cnt[a] / n) * (item_cnt[b] / n)})
    rules = rules[(rules["confidence"] >= MIN_CONFIDENCE) & (rules["lift"] >= MIN_LIFT)]
    return rules.sort_values(["lift", "confidence"], ascending=False).reset_index(drop=True), n


def market_basket_analysis(df):
    banner("8. MARKET BASKET ANALYSIS")
    n_all = df["trx_id"].nunique()
    sizes = df.groupby("trx_id")["produk"].nunique()
    print(f"Transaksi        : {n_all:,}")
    print(f"Basket >= 2 item : {(sizes >= 2).sum():,} ({100 * (sizes >= 2).mean():.1f}%)")

    rules, n_multi = _pair_rules(df, "produk")
    rules.to_csv(f"{OUTPUT_DIR}/basket_rules.csv", index=False)
    print(f"Aturan produk    : {len(rules):,} (support >= {MIN_SUPPORT}, confidence >= {MIN_CONFIDENCE}, lift >= {MIN_LIFT})")
    if len(rules):
        print(rules.head(15).round(4).to_string(index=False))
    else:
        print("Tidak ada pasangan produk yang muncul bersama lebih sering dari kebetulan.")

    old_support = MIN_SUPPORT
    globals()["MIN_SUPPORT"] = 0.002
    try:
        cat_rules, _ = _pair_rules(df, "kategori")
    finally:
        globals()["MIN_SUPPORT"] = old_support
    cat_rules.to_csv(f"{OUTPUT_DIR}/basket_rules_category.csv", index=False)
    print(f"\nAturan kategori  : {len(cat_rules):,}")
    if len(cat_rules):
        print(cat_rules.head(10).round(4).to_string(index=False))
    return rules, cat_rules
