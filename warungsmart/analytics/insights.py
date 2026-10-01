from .common import *

def generate_business_insights(df, elasticity, cat_elasticity, anomalies, rules, cat_rules,
                               metrics, next_week):
    banner("9. BUSINESS INSIGHTS")
    ins = {}
    ins["top_products_units"] = df.groupby("produk")["jumlah"].sum().nlargest(10).to_dict()
    ins["top_products_revenue"] = df.groupby("produk")["revenue"].sum().nlargest(10).to_dict()
    ins["top_products_profit"] = df.groupby("produk")["profit"].sum().nlargest(10).to_dict()
    ins["forecast_quality"] = metrics

    if len(cat_elasticity):
        ins["category_elasticity"] = cat_elasticity.set_index("kategori")[
            ["elasticity", "ci_low", "ci_high", "p_value", "reliable"]].to_dict("index")
    if len(elasticity):
        rel = elasticity[elasticity["reliable"]].head(10)
        ins["price_sensitive_products_significant"] = rel.set_index("produk")[
            ["elasticity", "ci_low", "ci_high"]].to_dict("index")

    if len(anomalies):
        ins["anomalies_by_type"] = anomalies["anomaly_type"].str.split(";").explode().value_counts().to_dict()
        ins["products_with_most_anomalies"] = anomalies.groupby("produk").size().nlargest(10).to_dict()
        below = anomalies[anomalies["anomaly_type"].str.contains("JUAL_DI_BAWAH_HPP")]
        ins["products_sold_below_cost"] = below.groupby("produk").size().nlargest(10).to_dict()

    if len(rules):
        ins["top_basket_rules"] = rules.head(10)[["antecedents", "consequents", "lift", "confidence"]].to_dict("records")
    if len(cat_rules):
        ins["top_category_rules"] = cat_rules.head(10)[["antecedents", "consequents", "lift", "confidence"]].to_dict("records")

    col = [c for c in next_week.columns if c.startswith("pred_")][0]
    ins[f"top_predicted_demand_{col}"] = (next_week.head(15)
                                          .assign(item=lambda x: x["warung_id"] + " | " + x["produk"])
                                          .set_index("item")[col].round(1).to_dict())

    with open(f"{OUTPUT_DIR}/business_insights.json", "w", encoding="utf-8") as f:
        json.dump(ins, f, indent=4, ensure_ascii=False, default=jsonable)
    print("Insight disimpan ke business_insights.json")
    return ins
