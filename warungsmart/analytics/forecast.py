from .common import *
from .demand import make_X

def _scores(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    err = y - p
    ss_tot = ((y - y.mean()) ** 2).sum()
    return {"MAE": float(np.abs(err).mean()),
            "RMSE": float(np.sqrt((err ** 2).mean())),
            "WAPE_%": float(100 * np.abs(err).sum() / max(y.sum(), 1e-9)),
            "Bias_%": float(100 * (p.sum() / max(y.sum(), 1e-9) - 1)),
            "R2": float(1 - (err ** 2).sum() / ss_tot) if ss_tot > 0 else float("nan")}


def _make_model():
    if HAS_XGB:
        return XGBRegressor(
            objective="count:poisson", eval_metric="poisson-nloglik",
            n_estimators=1500, learning_rate=0.05, max_depth=6, min_child_weight=5,
            subsample=0.8, colsample_bytree=0.8, tree_method="hist",
            enable_categorical=True, early_stopping_rounds=50,
            random_state=RANDOM_STATE, n_jobs=-1)
    return HistGradientBoostingRegressor(
        loss="poisson", learning_rate=0.06, max_iter=600, max_leaf_nodes=48,
        min_samples_leaf=40, l2_regularization=1.0, early_stopping=True,
        validation_fraction=0.1, n_iter_no_change=30,
        categorical_features="from_dtype", random_state=RANDOM_STATE)


def demand_forecasting(daily, future):
    banner(f"5. DEMAND FORECASTING (direct {FORECAST_HORIZON} hari)")
    print(f"Model : {'XGBoost (count:poisson)' if HAS_XGB else 'HistGradientBoosting (poisson) - xgboost tidak terpasang'}")
    data = daily.dropna(subset=["demand", "rmean_28"])

    dates = np.sort(data["tanggal"].unique())
    cut = dates[int(len(dates) * (1 - TEST_FRACTION)) - 1]
    train_all, test = data[data["tanggal"] <= cut], data[data["tanggal"] > cut]
    print(f"Split tanggal : train <= {str(cut)[:10]} | test > {str(cut)[:10]}")
    print(f"Train : {len(train_all):,} | Test : {len(test):,}")

    model = _make_model()
    X_test, y_test = make_X(test), test["demand"].values
    if HAS_XGB:
        tr_dates = np.sort(train_all["tanggal"].unique())
        vcut = tr_dates[int(len(tr_dates) * 0.9) - 1]
        tr, va = train_all[train_all["tanggal"] <= vcut], train_all[train_all["tanggal"] > vcut]
        model.fit(make_X(tr), tr["demand"].values,
                  eval_set=[(make_X(va), va["demand"].values)], verbose=False)
        print(f"Best iteration : {model.best_iteration}")
    else:
        model.fit(make_X(train_all), train_all["demand"].values)
    pred = np.maximum(model.predict(X_test), 0)

    # ---- metrik + pembanding (baseline) ----
    H = FORECAST_HORIZON
    naive_col = f"lag_{7 if H <= 7 else 7 * int(np.ceil(H / 7))}"
    rows = {"Model": _scores(y_test, pred),
            f"Naif ({naive_col})": _scores(y_test, test[naive_col].fillna(0)),
            "Rata2 28 hari": _scores(y_test, test["rmean_28"].fillna(0)),
            "Rata2 hari-sama": _scores(y_test, test["same_dow_mean"].fillna(0))}
    table = pd.DataFrame(rows).T
    print("\nMetrik level SKU-hari (makin kecil MAE/RMSE/WAPE makin baik):")
    print(table.round(4))
    base_best = table.drop(index="Model")["WAPE_%"].min()
    skill = 1 - table.loc["Model", "WAPE_%"] / base_best
    print(f"\nPerbaikan WAPE vs baseline terbaik: {100 * skill:.1f}%")

    result = test[["tanggal", "warung_id", "produk", "kategori"]].copy()
    result["jumlah"] = test["demand"].values
    result["prediction"] = pred
    result["error"] = result["jumlah"] - result["prediction"]
    agg = result.groupby(["warung_id", "tanggal"], as_index=False)[["jumlah", "prediction"]].sum()
    wape_agg = 100 * (agg["jumlah"] - agg["prediction"]).abs().sum() / agg["jumlah"].sum()
    print(f"WAPE total per warung-hari (level yang dipakai untuk pengadaan): {wape_agg:.2f}%")
    result.to_csv(f"{OUTPUT_DIR}/forecasts.csv", index=False)

    # ---- pentingnya fitur ----
    try:
        if HAS_XGB:
            imp = pd.Series(model.feature_importances_, index=X_test.columns)
        else:
            s = test.sample(min(15000, len(test)), random_state=RANDOM_STATE)
            pi = permutation_importance(model, make_X(s), s["demand"].values, n_repeats=1,
                                        random_state=RANDOM_STATE, scoring="neg_mean_absolute_error")
            imp = pd.Series(pi.importances_mean, index=X_test.columns)
        imp.sort_values(ascending=False).rename("importance").to_csv(f"{OUTPUT_DIR}/feature_importance.csv")
        print("\nFitur terpenting:", ", ".join(imp.sort_values(ascending=False).head(6).index))
    except Exception as exc:                                   # noqa: BLE001
        print(f"(feature importance dilewati: {exc})")

    # ---- plot ----
    day = result.groupby("tanggal")[["jumlah", "prediction"]].sum().reset_index()
    plt.figure(figsize=(14, 5))
    plt.plot(day["tanggal"], day["jumlah"], label="Actual")
    plt.plot(day["tanggal"], day["prediction"], label="Predicted", linestyle="--")
    plt.legend()
    plt.title(f"Demand Forecast (horizon {H} hari, total semua warung)")
    plt.tight_layout()
    plt.savefig(f"{OUTPUT_DIR}/forecast.png")
    plt.close()

    # ---- prediksi H hari ke depan (benar-benar masa depan) ----
    fut = future[["tanggal", "warung_id", "produk", "kategori"]].copy()
    fut["prediction"] = np.maximum(model.predict(make_X(future)), 0)
    fut.to_csv(f"{OUTPUT_DIR}/future_forecast.csv", index=False)
    summary = (fut.groupby(["warung_id", "produk", "kategori"], as_index=False)["prediction"].sum()
                  .rename(columns={"prediction": f"pred_{H}d"})
                  .sort_values(f"pred_{H}d", ascending=False))
    summary.to_csv(f"{OUTPUT_DIR}/future_forecast_summary.csv", index=False)
    print(f"Prediksi {H} hari ke depan disimpan ({str(fut['tanggal'].min())[:10]} s.d. {str(fut['tanggal'].max())[:10]})")

    metrics = {**{k: v for k, v in rows["Model"].items()},
               "WAPE_warung_hari_%": float(wape_agg),
               "baseline_WAPE_terbaik_%": float(base_best),
               "improvement_vs_baseline_%": float(100 * skill),
               "backend": "xgboost" if HAS_XGB else "hist_gradient_boosting"}
    return model, metrics, result, summary
