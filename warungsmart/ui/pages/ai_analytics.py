import json
from pathlib import Path
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/"outputs"
DATA=ROOT/"data"/"simulated"

def render(ctx):
    st.subheader("Retail AI Analytics")
    metrics=OUT/"metrics.json"
    if not metrics.exists():
        st.info("Belum ada hasil pipeline. Jalankan `python scripts/run_pipeline.py` terlebih dahulu.")
        return
    m=json.loads(metrics.read_text())
    c1,c2,c3,c4=st.columns(4)
    fm=m.get("forecasting",{})
    c1.metric("MAE", round(fm.get("MAE",0),3))
    c2.metric("RMSE", round(fm.get("RMSE",0),3))
    c3.metric("WAPE", f"{100*fm.get('WAPE',0):.2f}%")
    c4.metric("R²", round(fm.get("R2",0),3))
    tabs=st.tabs(["Forecast","Anomaly","Elasticity","Basket","Business Insights"])
    files=[("forecasts_test.csv",0),("anomalies.csv",1),("elasticity_category.csv",2),("basket_rules_category.csv",3),("business_insights.json",4)]
    for name,idx in files:
        with tabs[idx]:
            p=OUT/name
            if not p.exists(): st.warning(f"Output {name} belum tersedia."); continue
            if p.suffix==".json": st.json(json.loads(p.read_text()))
            else:
                df=pd.read_csv(p)
                st.dataframe(df.head(100),use_container_width=True)
