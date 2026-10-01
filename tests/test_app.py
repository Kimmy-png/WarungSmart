import pytest
from streamlit.testing.v1 import AppTest

from warungsmart import config

PAGES = ["▣ Dashboard", "＋ Transaksi", "▤ Persediaan", "✦ AI Insight", "◈ Tren Pasar", "🔒 Privasi Data"]


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_for_every_warung(page):
    at = AppTest.from_file(str(config.ROOT / "app.py"), default_timeout=30).run()
    assert not at.exception
    for wid in range(1, 7):
        at.session_state["nav"] = page
        at.session_state["warung"] = wid
        at.run()
        assert not at.exception, (page, wid, at.exception)
