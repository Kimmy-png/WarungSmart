from html import escape

import streamlit as st

from warungsmart.db import repository as repo
from warungsmart.services import analytics, insights, inventory, market, temporal
from warungsmart.ui import components as ui
from warungsmart.ui.context import AppContext
from warungsmart.ui.format import rupiah


def _go_ai():
    st.session_state["nav"] = "✦ AI Insight"


def render(ctx: AppContext) -> None:
    daily = temporal.to_daily(repo.get_sales(ctx.warung_id))
    products = repo.get_products(ctx.warung_id)
    ref = ctx.ref_date

    if ctx.ref_date < ctx.today:
        ui.info(f"Catatan hari ini belum diisi. Data terakhir: {ctx.ref_date:%d/%m/%Y}. "
                "Buka menu Transaksi untuk mencatat penjualan hari ini.")

    k = analytics.month_kpis(daily, ref)
    stock = inventory.stock_table(products, daily, ref)
    crit = int((stock["status"] == "Kritis").sum())
    c = st.columns(4)
    with c[0]: ui.kpi_card("Omzet Bulan Ini", rupiah(k["omzet"]))
    with c[1]: ui.kpi_card("Laba Bersih", rupiah(k["laba"]), "green")
    with c[2]: ui.kpi_card("Produk Terjual", f"{k['terjual']:,}".replace(",", "."))
    with c[3]: ui.kpi_card("Stok Kritis", f"{crit} produk", "red")

    left, right = st.columns([1.35, 1])
    with left:
        wk = analytics.weekly_performance(daily, ref)
        bars = "".join(f'<div class="label">{r.minggu} · {rupiah(r.omzet)}</div>'
                       f'<div class="bar"><i style="width:{r.pct:.0f}%"></i></div>' for r in wk.itertuples())
        ui.card("Performa Penjualan", bars)
    with right:
        ui.insight_card(insights.personal_insights(daily, products, ref)[:3])

    a, b, d = st.columns(3)
    with a:
        top = analytics.top_products(daily, ref)
        ui.card("Produk Terlaris", "".join(
            f"<p>{i}. {escape(r.produk)} — {r.qty} unit</p>" for i, r in enumerate(top.itertuples(), 1)))
    with b:
        rec = insights.price_recommendation(daily, products, ref)
        if rec:
            ui.card("Rekomendasi Harga",
                    f"<p>Margin <b>{escape(rec['produk'])}</b> {rec['margin']:.0%}, di bawah target. "
                    f"Pertimbangkan {rupiah(rec['harga_saat_ini'])} → <b>{rupiah(rec['harga_saran'])}</b>.</p>")
        else:
            ui.card("Rekomendasi Harga", "<p>Margin produk terlaris sudah sesuai target.</p>")
        st.button("Lihat analisis", key="goai", on_click=_go_ai, type="primary")
    with d:
        trends, _ = market.market_trends(temporal.to_daily(repo.get_sales()), ref)
        if len(trends):
            t = trends.iloc[0]
            ui.card("Insight Kolektif", "<p>Tren dari data anonim pengguna WarungSmart.</p>"
                    f"<p><b>{escape(t['Kategori'])} {'↑' if t['Perubahan'] >= 0 else '↓'} {abs(t['Perubahan']):.0f}%</b></p>")
        else:
            ui.card("Insight Kolektif", "<p>Belum cukup data anonim.</p>")
