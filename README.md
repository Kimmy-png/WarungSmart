# WarungSmart AI

WarungSmart is a synthetic-data retail intelligence project for small warung/retail businesses. It combines a 540-day multi-warung simulator, business/accounting logic, demand forecasting, anomaly detection, price elasticity, market basket analysis, cross-warung intelligence, and a Streamlit interface.

## Repository structure

- `warungsmart/simulation/` — synthetic retail data generator.
- `warungsmart/analytics/` — modular ML/statistical analytics pipeline.
- `warungsmart/business/` — accounting/inventory/business engine retained from the original project.
- `warungsmart/db/` — SQLite layer.
- `warungsmart/ui/` — Streamlit UI.
- `notebooks/` — research/experimentation layer; the original notebook is preserved as `00_original_WarungSmart.ipynb`.
- `data/simulated/` — generated simulation data and merged analytical dataset.
- `outputs/` — pipeline results.
- `scripts/` — reproducible data-generation and pipeline commands.

## Included simulated data

The source notebook generated 6 warungs, 272 master SKUs, 540 days, 508,156 sales rows, 33,450 purchase records, 16,278 stockout events, and 2,148 price changes. The generated CSVs are included under `data/simulated/`.

## Run

```bash
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/build_merged_data.py
python scripts/run_pipeline.py
streamlit run app.py
```

The simulator is deterministic per its configured seeds. Running generation again replaces the simulated CSVs with a fresh deterministic run using the same configuration.
