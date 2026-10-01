import streamlit as st

from warungsmart.db import repository as repo
from warungsmart.services import inventory, temporal
from warungsmart.ui.context import AppContext

_ICON = {"Kritis": "🔴 Kritis", "Menipis": "🟠 Menipis", "Aman": "🟢 Aman"}


def render(ctx: AppContext) -> None:
    products = repo.get_products(ctx.warung_id)
    daily = temporal.to_daily(repo.get_sales(ctx.warung_id))
    t = inventory.stock_table(products, daily, ctx.ref_date)

    view = t.assign(
        Status=t["status"].map(_ICON),
        sisa=t["sisa_hari"].replace(float("inf"), None).round(1),
        rata=t["rata_harian"].round(1),
        saran=t["restock"].map(lambda q: f"Restock {q}" if q else "—"),
    )[["nama", "kategori", "stok", "rata", "sisa", "Status", "saran"]]
    view.columns = ["Produk", "Kategori", "Stok", "Rata-rata/hari", "Sisa (hari)", "Status", "Saran AI"]

    st.markdown('<div class="wcard"><h2>Persediaan & Restock</h2>'
                '<p class="label">Saran restock menargetkan stok cukup untuk 10 hari.</p></div>',
                unsafe_allow_html=True)
    st.dataframe(view, hide_index=True, width="stretch")

    with st.expander("Catat stok masuk"):
        c = st.columns([2, 1])
        nama = c[0].selectbox("Produk", products["nama"])
        qty = c[1].number_input("Jumlah masuk", min_value=1, value=10)
        if st.button("Tambah stok", type="primary"):
            pid = int(products.loc[products["nama"] == nama, "id"].iloc[0])
            repo.add_stock(ctx.warung_id, pid, int(qty))
            st.toast(f"Stok {nama} bertambah {qty}.")
            st.rerun()
