from .common import *

def anomaly_detection(daily):
    banner("6. ANOMALY DETECTION")
    feat_cols = ["z_qty", "price_chg_1", "margin_pct", "price_rel_28"]
    data = daily.dropna(subset=feat_cols).copy()

    # fitur bebas-skala: harga mutlak / jumlah mutlak TIDAK dipakai
    F = data[feat_cols].clip(lower=[-10, -0.5, -0.5, 0.5], upper=[10, 0.5, 0.8, 1.5], axis=1)
    model = IsolationForest(n_estimators=300, contamination=ANOMALY_RATE,
                            random_state=RANDOM_STATE, n_jobs=-1)
    ml_flag = model.fit_predict(F) == -1
    data["anomaly_score"] = model.decision_function(F)

    rules = {
        "LONJAKAN_PENJUALAN": (data["z_qty"] >= Z_QTY_THRESHOLD) & (data["demand"] >= 5),
        "PENURUNAN_TAJAM": (data["z_qty"] <= -Z_QTY_THRESHOLD) & (data["rm28_1"] >= 5),
        "JUAL_DI_BAWAH_HPP": (data["jumlah"] > 0) & (data["harga_jual"] < data["harga_beli"]),
        "LONJAKAN_HARGA": data["price_chg_1"].abs() >= PRICE_JUMP_THRESHOLD,
    }
    data["anomaly_type"] = ""
    for name, mask in rules.items():
        data.loc[mask, "anomaly_type"] = data.loc[mask, "anomaly_type"] + name + ";"
    only_ml = ml_flag & (data["anomaly_type"] == "")
    data.loc[only_ml, "anomaly_type"] = "POLA_TIDAK_BIASA;"
    data["anomaly_type"] = data["anomaly_type"].str.rstrip(";")

    anomalies = data[data["anomaly_type"] != ""].sort_values("anomaly_score")
    keep = ["tanggal", "warung_id", "produk", "kategori", "jumlah", "demand", "harga_jual",
            "harga_beli", "z_qty", "price_chg_1", "margin_pct", "anomaly_type", "anomaly_score"]
    anomalies = anomalies[keep]
    anomalies.to_csv(f"{OUTPUT_DIR}/anomalies.csv", index=False)

    print(f"Baris dianalisis : {len(data):,}")
    print(f"Anomali          : {len(anomalies):,} ({100 * len(anomalies) / len(data):.2f}%)")
    counts = {name: int(mask.sum()) for name, mask in rules.items()}
    counts["POLA_TIDAK_BIASA (hanya ML)"] = int(only_ml.sum())
    for k, v in counts.items():
        print(f"  {k:<30}{v:>8,}")
    return model, anomalies
