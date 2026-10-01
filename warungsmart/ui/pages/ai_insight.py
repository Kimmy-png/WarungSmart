import pandas as pd
import streamlit as st

from warungsmart.db import repository as repo
from warungsmart.services import insights, temporal
from warungsmart.ui import components as ui
from warungsmart.ui.context import AppContext
from warungsmart.ui.format import rupiah


def render(ctx: AppContext) -> None:
    daily = temporal.to_daily(repo.get_sales(ctx.warung_id))
    products = repo.get_products(ctx.warung_id)
    ui.insight_card(insights.personal_insights(daily, products, ctx.ref_date), "✦ AI Personal Insight")

    fc = insights.forecast_revenue(daily, ctx.ref_date)
    if fc:
        st.markdown('<div class="wcard"><h2>Prakiraan Omzet 30 Hari</h2>'
                    f'<p>Kisaran <b>{rupiah(fc["low"])} – {rupiah(fc["high"])}</b> '
                    f'(titik tengah {rupiah(fc["mid"])})</p></div>', unsafe_allow_html=True)
        chart = pd.concat([fc["history"].rename("Aktual"), fc["future"].rename("Prakiraan")], axis=1)
        st.line_chart(chart, height=260)

    if temporal.hourly_profile(repo.get_sales(ctx.warung_id)) is None:
        ui.info("Analisis jam sibuk tidak tersedia karena pencatatan dilakukan harian. "
                "Fitur ini aktif otomatis bila data per jam tersedia.")
