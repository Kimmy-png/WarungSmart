from pathlib import Path
import pandas as pd
base=Path("data/simulated")
out=base/"data_simulasi_gabungan.csv"
sales=pd.read_csv(base/"penjualan.csv")
warung=pd.read_csv(base/"warung.csv")
cal=pd.read_csv(base/"kalender.csv")
df=sales.merge(warung,on="warung_id",how="left").merge(cal,on="tanggal",how="left")
df.to_csv(out,index=False)
print(f"Saved {len(df):,} rows -> {out}")
