"""Shared configuration/state for the notebook-derived analytics pipeline."""
import os, json, warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import sparse, stats
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest
from sklearn.inspection import permutation_importance
try:
    from xgboost import XGBRegressor
    HAS_XGB=True
except ImportError:
    HAS_XGB=False
warnings.filterwarnings("ignore")

DATA_PATH=os.environ.get("RETAIL_DATA_PATH", "data/simulated/data_simulasi_gabungan.csv")
STOCKOUT_PATH=os.environ.get("RETAIL_STOCKOUT_PATH", "data/simulated/stockout.csv")
OUTPUT_DIR=os.environ.get("RETAIL_OUTPUT_DIR", "outputs")
FORECAST_HORIZON=7
TEST_FRACTION=0.20
CORRECT_STOCKOUT=True
USE_WEATHER=False
GAJIAN_DAYS={25,26,1}
ANOMALY_RATE=0.005
Z_QTY_THRESHOLD=4.0
PRICE_JUMP_THRESHOLD=0.15
MIN_SUPPORT=0.0005
MIN_CONFIDENCE=0.02
MIN_LIFT=1.10
MIN_PAIR_COUNT=20
RANDOM_STATE=42
KEYS=["warung_id","produk"]
CAT_COLS=["warung_id","kategori","fase_akademik"]
REQUIRED_COLS=["warung_id","trx_id","tanggal","produk","kategori","jumlah","harga_jual","harga_beli","hujan","akhir_pekan","libur_nasional","gajian"]
META={"categories":{},"numeric":[]}
os.makedirs(OUTPUT_DIR, exist_ok=True)

def banner(title):
    print("\n"+"="*70); print(title); print("="*70)

def jsonable(o):
    if isinstance(o,np.integer): return int(o)
    if isinstance(o,np.floating): return None if np.isnan(o) else float(o)
    if isinstance(o,(pd.Timestamp,np.datetime64)): return str(o)[:10]
    raise TypeError(f"tidak bisa serialisasi {type(o)}")
