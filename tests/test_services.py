from datetime import timedelta

import pytest

from warungsmart import config
from warungsmart.db import repository as repo
from warungsmart.db import seed
from warungsmart.services import analytics, insights, inventory, market, temporal


@pytest.fixture(autouse=True)
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    seed.ensure_seeded()


def _ref(daily):
    return daily["tanggal"].max().date()


def test_six_warung():
    assert len(repo.list_warung()) == 6


def test_daily_save_is_idempotent_and_adjusts_stock():
    pid = int(repo.get_products(1).iloc[0]["id"])
    before = int(repo.get_products(1).set_index("id").loc[pid, "stok"])
    day = config.today()
    repo.save_daily_sales(1, day, {pid: 4})
    repo.save_daily_sales(1, day, {pid: 4})
    assert repo.get_daily_entries(1, day)[pid] == 4
    assert int(repo.get_products(1).set_index("id").loc[pid, "stok"]) == max(0, before - 4)


def test_hourly_disabled_and_db_has_nullable_hour():
    s = repo.get_sales(1)
    assert s["jam"].isna().all()
    assert temporal.hourly_profile(s) is None


def test_services_run():
    s = temporal.to_daily(repo.get_sales(1))
    ref = _ref(s)
    assert analytics.month_kpis(s, ref)["omzet"] > 0
    assert len(inventory.stock_table(repo.get_products(1), s, ref)) == 12
    assert insights.personal_insights(s, repo.get_products(1), ref)
    assert insights.forecast_revenue(s, ref)["low"] <= insights.forecast_revenue(s, ref)["high"]


def test_market_k_anonymity_hides_small_categories():
    s = temporal.to_daily(repo.get_sales())
    t, hidden = market.market_trends(s, _ref(s))
    assert "Produk Musiman" in set(t["Kategori"])       # 4 warung >= k
    assert "warung" not in " ".join(t.columns).lower() or "Sampel" in " ".join(t.columns)
    config.K_ANON_MIN_WARUNG = 5
    t2, hidden2 = market.market_trends(s, _ref(s))
    config.K_ANON_MIN_WARUNG = 3
    assert "Produk Musiman" not in set(t2["Kategori"]) and hidden2 >= 1
