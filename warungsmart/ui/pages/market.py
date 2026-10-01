import streamlit as st

from warungsmart.db import repository as repo
from warungsmart.services import market, temporal
from warungsmart.ui import components as ui
from warungsmart.ui.context import AppContext


def render(ctx: AppContext) -> None:
    daily = temporal.to_daily(repo.get_sales())          # semua warung -> hanya diagregasi
    ref = daily["tanggal"].max().date()
    trends, hidden = market.market_trends(daily, ref)

    st.markdown('<div class="wcard"><h2>◈ AI Market Insight — Data Agregat</h2></div>', unsafe_allow_html=True)
    ui.note("Insight berasal dari pola gabungan data pengguna yang telah dianonimkan dan diagregasi. "
            "Tidak ada nama warung, omzet individual, atau transaksi warung lain yang ditampilkan.")
    st.dataframe(
        trends, hide_index=True, width="stretch",
        column_config={"Perubahan": st.column_config.NumberColumn(format="%+.0f%%")})
    if hidden:
        st.caption(f"{hidden} kategori disembunyikan karena kontributornya kurang dari "
                   f"{market.config.K_ANON_MIN_WARUNG} warung (melindungi privasi).")
