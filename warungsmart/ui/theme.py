"""CSS yang menerjemahkan frontend HTML asli ke Streamlit."""
import streamlit as st

CSS = """
<style>
.stApp{background:#f5f7fb;color:#172033}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:1.6rem;max-width:1200px}
[data-testid="stSidebar"]{background:#102a43}
[data-testid="stSidebar"] *{color:#dce8f4}
[data-testid="stSidebar"] [data-baseweb="select"] *{color:#172033}
[data-testid="stSidebar"] [role="radiogroup"]{gap:2px}
[data-testid="stSidebar"] [role="radiogroup"] label{padding:10px 12px;border-radius:10px;width:100%}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{background:#1d4668}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){background:#1d4668}
[data-testid="stSidebar"] [role="radiogroup"] label > div:first-child{display:none}
.brand{font-size:23px;font-weight:800;margin:0 4px 4px;color:#fff}
.tag{font-size:12px;color:#b8c7d9;margin:0 4px 22px}
.privacy-box{margin-top:22px;padding:12px;background:#173c5c;border-radius:12px;font-size:11px;line-height:1.5}
.sub{color:#6b778c;font-size:13px;margin-top:4px}
.ws-title{font-size:25px;font-weight:800;margin:0}
.badge{background:#e7f6ed;color:#16734b;padding:8px 12px;border-radius:999px;font-size:12px;font-weight:700;float:right}
.wcard{background:#fff;border:1px solid #e7ebf1;border-radius:14px;padding:18px;box-shadow:0 2px 8px #17203308;margin-bottom:14px}
.wcard h2{font-size:17px;margin:0 0 12px;font-weight:700}
.wcard p{margin:6px 0;font-size:14px}
.label{font-size:12px;color:#738096}
.value{font-size:24px;font-weight:800;margin-top:6px}
.green{color:#168052}.orange{color:#c87813}.red{color:#c83b4b}
.ai{background:linear-gradient(135deg,#edf8ff,#f8f2ff);border:1px solid #d8e9f7}
.insight{padding:11px 0;border-bottom:1px solid #edf0f4;font-size:13px;line-height:1.5}
.insight:last-child{border:0}.insight strong{display:block;margin-bottom:3px}
.bar{height:9px;background:#e9eef4;border-radius:9px;overflow:hidden;margin-bottom:12px}
.bar i{display:block;height:100%;background:#1f6feb;border-radius:9px}
.note{background:#fff8e7;border:1px solid #f1dfac;padding:14px;border-radius:12px;font-size:13px;line-height:1.5;margin-bottom:12px}
.empty{background:#eef5ff;border:1px solid #cfe0f7;padding:12px 14px;border-radius:12px;font-size:13px;margin-bottom:14px}
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
