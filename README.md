# WarungSmart AI

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white" alt="Streamlit UI" />
  <img src="https://img.shields.io/badge/AI-%26%20Forecasting-Enabled-00C7B7" alt="AI Forecasting Enabled" />
</p>

WarungSmart AI is a synthetic retail intelligence project built for small warung and neighborhood retail businesses. It combines simulated transaction data, business logic, demand forecasting, anomaly detection, and a Streamlit-based dashboard to help simulate real operational decisions in a privacy-safe environment.

This project is designed to:

- generate realistic retail transaction data for multiple stores
- model inventory, stockouts, pricing, and daily business operations
- provide forecasting and analytical insights for demand and operational risk
- expose the results through a local dashboard and analysis workflow

## Highlights

- Synthetic retail data generation across multiple warungs
- 540-day simulation of business operations
- Sales, inventory, stockouts, and pricing event modeling
- Machine learning and statistical analytics pipeline
- Streamlit dashboard for business monitoring and insights
- Deterministic simulation output for reproducible experiments

## Included dataset

The generated synthetic dataset includes:

- 6 warungs
- 272 master SKUs
- 540 days of simulated operations
- 508,156 sales rows
- 33,450 purchase records
- 16,278 stockout events
- 2,148 price changes

The data is generated deterministically from configured seeds, which makes experiments reproducible when using the same setup.

## Project structure

```text
WarungSmart/
├── app.py                    # Streamlit application entry point
├── README.md                # Project documentation
├── requirements.txt         # Python dependencies
├── requirements-dev.txt     # Development dependencies
├── .streamlit/              # Streamlit configuration
├── data/                    # Simulated and merged datasets
├── models/                  # Model-related artifacts
├── notebooks/               # Research and exploratory notebooks
├── outputs/                 # Pipeline outputs and evaluation artifacts
├── scripts/                 # Reproducible generation and pipeline scripts
├── tests/                   # Test suite
├── warungsmart/             # Core application package
│   ├── analytics/           # Forecasting and analytics modules
│   ├── business/            # Business/accounting logic
│   ├── db/                  # SQLite and data-access layer
│   ├── simulation/          # Synthetic data simulator
│   └── ui/                  # Streamlit UI components and styling
└── 00_original_WarungSmart.ipynb
```

## Repository modules

- `warungsmart/simulation/` — synthetic retail data generator
- `warungsmart/analytics/` — modular analytics and forecasting pipeline
- `warungsmart/business/` — accounting, inventory, and operational business logic
- `warungsmart/db/` — SQLite-backed persistence layer
- `warungsmart/ui/` — Streamlit interface and dashboard screens
- `notebooks/` — experimentation and research notebooks
- `data/simulated/` — generated and merged retail datasets
- `outputs/` — results from the analytics pipeline
- `scripts/` — automation scripts for data generation and pipeline execution

## Quick start

1. Create and activate a virtual environment (optional but recommended):

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

4. Build the merged dataset:

```bash
python scripts/build_merged_data.py
```

5. Run the analytics pipeline:

```bash
python scripts/run_pipeline.py
```

6. Start the app:

```bash
streamlit run app.py
```

## Usage

After launching the app, the dashboard lets you explore:

- daily transaction trends
- inventory and stockout conditions
- operational performance
- AI-powered insights
- market and retail analytics
- privacy-aware business reporting

## Notes

- The simulator is deterministic for a fixed configuration and seed set.
- Re-running generation replaces the existing simulated CSV outputs with a fresh deterministic run.
- The project is intended for local experimentation, analysis, and demo use.

## License

This project does not currently declare a license file in the repository root. If you plan to distribute or reuse it publicly, consider adding an appropriate open-source license.

## Project status

This repository is structured as a synthetic retail analytics and forecasting prototype, with the main user-facing experience delivered through the Streamlit app in `app.py`.
