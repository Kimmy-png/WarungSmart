import streamlit as st

from warungsmart import config
from warungsmart.ui import components as ui
from warungsmart.ui.context import AppContext


def render(ctx: AppContext) -> None:
    st.markdown(f"""<div class="wcard"><h2>🔒 Privasi & Keamanan Data</h2>
<p><b>Data warung Anda bersifat privat.</b></p><ul>
<li>Transaksi dan omzet hanya dapat diakses akun yang berwenang.</li>
<li>Warung lain tidak dapat membuka data individual Anda.</li>
<li>AI Market Insight memakai data anonim dan agregat.</li>
<li>Insight berisiko mengungkap satu warung tidak ditampilkan (minimal {config.K_ANON_MIN_WARUNG} warung per kategori).</li>
<li>Hak akses dibatasi berdasarkan peran pengguna.</li></ul></div>""", unsafe_allow_html=True)
    ui.note("<b>Prinsip utama:</b> semakin banyak data terkumpul, semakin kaya insight — "
            "tetapi data individual tetap berada di ruang privat pemiliknya.")
    ui.info("Mode demo: pemilik dapat berpindah antar warung lewat menu samping. "
            "Pada versi produksi, perpindahan ini diganti login per pemilik.")
