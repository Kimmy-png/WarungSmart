"""Entrypoint Streamlit: `streamlit run app.py`"""
import streamlit as st

from warungsmart import config
from warungsmart.db import repository as repo
from warungsmart.db.seed import ensure_seeded
from warungsmart.ui import theme
from warungsmart.ui.context import AppContext
from warungsmart.ui.format import tanggal_id
from warungsmart.ui.pages import ai_insight, ai_analytics, dashboard, market, privasi, stok, transaksi

st.set_page_config(page_title="WarungSmart AI", page_icon="🛒", layout="wide")


PAGES = {
    "▣ Dashboard": ("Dashboard Warung", dashboard.render),
    "＋ Transaksi": ("Pencatatan Transaksi Harian", transaksi.render),
    "▤ Persediaan": ("Persediaan", stok.render),
    "✦ AI Insight": ("AI Personal Insight", ai_insight.render),
    "◉ Retail AI": ("Retail AI Analytics", ai_analytics.render),
    "◈ Tren Pasar": ("AI Market Insight", market.render),
    "🔒 Privasi Data": ("Privasi & Keamanan Data", privasi.render),
}

ensure_seeded()   # murah: buat skema bila belum ada, isi data demo bila kosong
theme.inject()

warung = repo.list_warung()
with st.sidebar:
    st.markdown('<div class="brand">WarungSmart AI</div>'
                '<div class="tag">Smart Accounting × Management</div>', unsafe_allow_html=True)
    st.session_state.setdefault("nav", "▣ Dashboard")
    page = st.radio("Menu", list(PAGES), key="nav", label_visibility="collapsed")
    st.markdown("---")
    wid = st.selectbox("Tampilan warung", warung["id"], key="warung",
                       format_func=lambda i: warung.set_index("id").loc[i, "nama"])
    st.markdown('<div class="privacy-box"><b>PRIVATE BY DESIGN</b><br>Data transaksi warung hanya dapat '
                'dilihat oleh pemilik akun. Insight lintas warung memakai data anonim &amp; agregat.</div>',
                unsafe_allow_html=True)

name = warung.set_index("id").loc[wid, "nama"]
sales = repo.get_sales(int(wid))
ref = sales["tanggal"].max().date() if not sales.empty else config.today()
ctx = AppContext(int(wid), name, config.today(), ref)

title, render = PAGES[page]
c1, c2 = st.columns([4, 1])
c1.markdown(f'<p class="ws-title">{title}</p><div class="sub">{name} • {tanggal_id(ctx.today)}</div>',
            unsafe_allow_html=True)
c2.markdown('<span class="badge">● Sistem aktif</span>', unsafe_allow_html=True)
render(ctx)
