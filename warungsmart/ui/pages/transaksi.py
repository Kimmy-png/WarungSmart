import pandas as pd
import streamlit as st

from warungsmart.db import repository as repo
from warungsmart.services import temporal
from warungsmart.ui import components as ui
from warungsmart.ui.context import AppContext
from warungsmart.ui.format import rupiah, tanggal_id


def render(ctx: AppContext) -> None:
    products = repo.get_products(ctx.warung_id)
    ver = st.session_state.setdefault("tx_ver", 0)

    st.markdown('<div class="wcard"><h2>Catatan Penjualan Harian</h2>'
                '<p class="label">Isi jumlah terjual per produk untuk satu hari. '
                'Menyimpan ulang tanggal yang sama akan menggantikan catatan sebelumnya.</p></div>',
                unsafe_allow_html=True)
    tgl = st.date_input("Tanggal", value=ctx.today, max_value=ctx.today, key=f"tgl_{ctx.warung_id}")
    existing = repo.get_daily_entries(ctx.warung_id, tgl)

    table = pd.DataFrame({
        "id": products["id"], "Produk": products["nama"], "Harga": products["harga_jual"],
        "Stok": products["stok"], "Terjual": products["id"].map(existing).fillna(0).astype(int),
    })
    edited = st.data_editor(
        table, hide_index=True, width="stretch",
        key=f"editor_{ctx.warung_id}_{tgl}_{ver}", disabled=["Produk", "Harga", "Stok"],
        column_config={
            "id": None,
            "Harga": st.column_config.NumberColumn(format="Rp%d"),
            "Terjual": st.column_config.NumberColumn("Terjual (unit)", min_value=0, step=1),
        })
    est = float((edited["Terjual"] * edited["Harga"]).sum())
    st.caption(f"{tanggal_id(tgl)} · estimasi omzet {rupiah(est)}")

    if st.button("Simpan catatan harian", type="primary"):
        n = repo.save_daily_sales(ctx.warung_id, tgl, dict(zip(edited["id"], edited["Terjual"])))
        st.session_state["tx_ver"] = ver + 1
        st.toast(f"Catatan tersimpan ({n} produk diperbarui). Insight AI diperbarui.")
        st.rerun()

    with st.expander("Tambah produk baru"):
        c = st.columns(3)
        nama = c[0].text_input("Nama produk")
        kat = c[1].text_input("Kategori", placeholder="mis. Minuman Dingin")
        stok = c[2].number_input("Stok awal", min_value=0, value=0)
        c = st.columns(2)
        beli = c[0].number_input("Harga beli (Rp)", min_value=0, step=100)
        jual = c[1].number_input("Harga jual (Rp)", min_value=0, step=100)
        if st.button("Tambah produk"):
            if not nama.strip() or not kat.strip() or jual <= 0:
                st.error("Nama, kategori, dan harga jual wajib diisi.")
            else:
                try:
                    repo.add_product(ctx.warung_id, nama, kat, beli, jual, int(stok))
                    st.session_state["tx_ver"] = ver + 1
                    st.rerun()
                except Exception:
                    st.error("Produk dengan nama itu sudah ada di warung ini.")

    daily = temporal.to_daily(repo.get_sales(ctx.warung_id))
    hist = (daily.groupby("tanggal")[["total", "qty"]].sum().sort_index(ascending=False).head(7)
            .reset_index())
    hist["Tanggal"] = hist["tanggal"].dt.date.map(tanggal_id)
    hist["Omzet"] = hist["total"].map(rupiah)
    st.markdown('<div class="wcard"><h2>Riwayat 7 Hari Terakhir</h2></div>', unsafe_allow_html=True)
    st.dataframe(hist[["Tanggal", "qty", "Omzet"]].rename(columns={"qty": "Unit terjual"}),
                 hide_index=True, width="stretch")
