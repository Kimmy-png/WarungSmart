"""End-to-end orchestration of the notebook-derived retail AI pipeline."""
import json, os
from .common import *
from .data import load_data, load_stockout, clean_data, run_eda
from .demand import create_demand_dataset
from .forecast import demand_forecasting
from .anomaly import anomaly_detection
from .elasticity import estimate_price_elasticity
from .basket import market_basket_analysis
from .insights import generate_business_insights

def run_pipeline(data_path=DATA_PATH, stockout_path=STOCKOUT_PATH, output_dir=OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    df=clean_data(load_data(data_path))
    run_eda(df)
    stockout=load_stockout(stockout_path)
    daily,future=create_demand_dataset(df,stockout)
    model,metrics,forecasts,next_week=demand_forecasting(daily,future)
    _,anomalies=anomaly_detection(daily)
    elasticity,cat_elasticity=estimate_price_elasticity(daily)
    rules,cat_rules=market_basket_analysis(df)
    insights=generate_business_insights(df,elasticity,cat_elasticity,anomalies,rules,cat_rules,metrics,next_week)
    result={"model":model,"metrics":metrics,"forecasts":forecasts,"next_week":next_week,"anomalies":anomalies,"elasticity":elasticity,"category_elasticity":cat_elasticity,"basket_rules":rules,"category_basket_rules":cat_rules,"insights":insights}
    pipeline_metrics={"forecasting":metrics,"forecast_horizon_days":FORECAST_HORIZON,"n_rows_original":int(len(df)),"n_rows_daily_grid":int(len(daily)),"n_anomalies":int(len(anomalies)),"n_elasticity_products":int(len(elasticity)),"n_elasticity_significant":int(elasticity["reliable"].sum()) if len(elasticity) else 0,"n_association_rules":int(len(rules))}
    with open(os.path.join(output_dir,"metrics.json"),"w",encoding="utf-8") as f: json.dump(pipeline_metrics,f,indent=4,default=jsonable)
    return result

def main():
    banner("WARUNGSMART RETAIL AI PIPELINE")
    result=run_pipeline()
    banner("PIPELINE COMPLETED")
    for name in sorted(os.listdir(OUTPUT_DIR)): print("  ✓",name)
    return result

if __name__=="__main__": main()
