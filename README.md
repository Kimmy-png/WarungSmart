# WarungSmart AI

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit UI" />
  <img src="https://img.shields.io/badge/AI-%26%20Forecasting-Enabled-00C7B7" alt="AI Forecasting Enabled" />
</p>

WarungSmart AI is a synthetic retail intelligence project for small neighborhood stores (warung). It combines generated transaction data, accounting logic, inventory tracking, and AI-based forecasting into a local dashboard for operational decision making.

The project is designed to:

- generate realistic retail data for multiple stores
- simulate daily sales, stockouts, pricing, and inventory behavior
- model demand forecasting and business anomalies
- expose results through a Streamlit dashboard and analytics workflow

## Highlights

- Synthetic retail data generation across multiple warungs
- 540-day simulated operations dataset
- Sales, inventory, stockouts, pricing, and promotion modeling
- Forecasting and analytics pipeline
- Streamlit dashboard for monitoring and insights
- Deterministic demo dataset for reproducible experiments

## Included dataset

The generated synthetic dataset includes:

- 6 warungs
- 272 master SKUs
- 540 days of simulated operations
- 508,156 sales rows
- 33,450 purchase records
- 16,278 stockout events
- 2,148 price changes

The simulation is deterministic for a fixed configuration and seed, so experiments remain reproducible with the same setup.

## Repository structure

```text
WarungSmart/
├── app.py                       # Streamlit application entry point
├── README.md                   # Project documentation
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Development dependencies
├── .streamlit/                 # Streamlit configuration
├── data/                       # Simulated and merged dataset files
├── models/                     # Model artifacts placeholder
├── notebooks/                  # Research and exploratory notebooks
├── outputs/                    # Pipeline outputs and evaluation artifacts
├── scripts/                    # Data generation and pipeline scripts
├── tests/                      # Test suite
├── warungsmart/                # Core application package
│   ├── analytics/              # Forecasting and analytics modules
│   ├── business/               # Business and accounting logic
│   ├── db/                     # SQLite persistence layer
│   ├── simulation/             # Synthetic data simulator
│   └── ui/                     # Streamlit UI components and styling
├── 00_original_WarungSmart.ipynb
└── .gitignore
```

## Main modules

- `warungsmart/simulation/` — synthetic retail data generator
- `warungsmart/analytics/` — demand forecasting, evaluation, and business analytics
- `warungsmart/business/` — accounting and operational business logic
- `warungsmart/db/` — SQLite-backed persistence layer
- `warungsmart/ui/` — dashboard pages, styling, and UI helpers
- `notebooks/` — experimentation and analysis notebooks
- `data/simulated/` — generated retail dataset inputs
- `outputs/` — generated AI and analytics outputs
- `scripts/` — automation scripts for data generation and pipeline execution

## Quick start

1. Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# or
.venv\Scripts\activate      # Windows
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Generate the synthetic data:

```bash
python scripts/generate_data.py
```

4. Build or merge the dataset:

```bash
python scripts/build_merged_data.py
```

5. Run the analytics pipeline:

```bash
python scripts/run_pipeline.py
```

This step creates the files under `outputs/`, including forecast and analytics artifacts such as:

- `forecasts.csv`
- `future_forecast.csv`
- `future_forecast_summary.csv`
- `anomalies.csv`
- `elasticity_category.csv`
- `basket_rules_category.csv`
- `business_insights.json`
- `metrics.json`

6. Start the app:

```bash
streamlit run app.py
```

## Dashboard usage

After launching the app, the dashboard includes:

- Dashboard overview
- Transaction recording
- Inventory management
- AI personal insight
- Retail AI analytics
- Market trend analysis
- Data privacy and security page

The AI Analytics page reads the generated outputs from `outputs/` and shows them in tabs such as:

- Forecast
- Anomaly
- Elasticity
- Basket
- Business Insights

## Notes

- The simulator is deterministic for a fixed configuration and seed.
- Re-running generation replaces existing simulated CSV outputs with a fresh deterministic run.
- The pipeline must be executed before opening the AI analytics dashboard to populate the output files.
- This project is intended for local experimentation, analysis, and demo use.

## License

This project does not currently declare a license file at the repository root. If you plan to distribute or reuse it publicly, consider adding an appropriate open-source license.

## Project status

This repository is structured as a synthetic retail analytics and forecasting prototype, with the main user-facing experience delivered through the Streamlit app in `app.py`.
