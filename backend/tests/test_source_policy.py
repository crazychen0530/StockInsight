"""Local temporary config and simulated upstreams; never writes developer data."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from httpx2 import ASGITransport, AsyncClient

from app.collectors.errors import ProviderError, ProviderTimeoutError
from app.collectors.provider import MarketDataBatch
from app.collectors.source_policy import PolicyProvider
from app.core.config import Settings
from app.core.errors import ApplicationError
from app.jobs.collection import SourceProvider
from app.jobs.scheduler import ReadyProvider
from app.main import create_app
from app.repositories.source_policy import SourcePolicyRepository
from tests.test_daily_price_service import END, FETCHED, START, bar

TOKEN = "simulated-admin-credential-0123456789"


def test_config_defaults_atomic_save_conflict_and_corruption(tmp_path):
    store = SourcePolicyRepository(str(tmp_path))
    assert store.read().mode == "prefer_eastmoney"
    assert store.save("tencent", 0).revision == 1
    assert SourcePolicyRepository(str(tmp_path)).read().mode == "tencent"
    with pytest.raises(ApplicationError) as caught:
        store.save("eastmoney", 0)
    assert caught.value.code == "source_policy_conflict"
    assert store.read().mode == "tencent"
    store.path.write_text('{"mode":"malicious"}')
    with pytest.raises(ApplicationError) as caught:
        store.read()
    assert caught.value.code == "source_policy_unavailable"
    assert not list(tmp_path.glob("tmp*"))


def test_nonexistent_config_directory_is_not_silently_defaulted(tmp_path):
    with pytest.raises(ApplicationError):
        SourcePolicyRepository(str(tmp_path / "missing")).read()


def provider(tmp_path, outcomes, *, calendar=None):
    calls = []

    class Fake:
        def __init__(self, settings):
            self.interface = settings.market_data_daily_interface
            self.daily_source = "akshare" if self.interface == "stock_zh_a_hist" else "akshare_tx"

        def fetch_daily_prices(self, *args):
            calls.append(self.interface)
            result = outcomes.get(self.interface, (bar(day=END),))
            if isinstance(result, Exception):
                raise result
            return MarketDataBatch(tuple(result), self.daily_source, "fixture_simulated", FETCHED)

    result = PolicyProvider(
        Settings(source_policy_directory=str(tmp_path)), calendar=calendar, factory=Fake
    )
    return result, calls


def test_primary_success_never_requests_backup_and_live_policy_reload(tmp_path):
    result, calls = provider(tmp_path, {})
    batch = SourceProvider(result, "akshare").fetch_daily_prices("000001.SZ", START, END)
    assert batch.source == "akshare"
    assert calls == ["stock_zh_a_hist"]
    SourcePolicyRepository(str(tmp_path)).save("tencent", 0)
    batch = SourceProvider(result, "akshare").fetch_daily_prices("000001.SZ", START, END)
    assert batch.source == "akshare_tx"
    assert calls == ["stock_zh_a_hist", "stock_zh_a_hist_tx"]


@pytest.mark.parametrize("bad", [ProviderTimeoutError(), (), (replace(bar(), close=-1),)])
def test_timeout_empty_and_invalid_primary_fallback_preserves_source(tmp_path, bad):
    result, calls = provider(tmp_path, {"stock_zh_a_hist": bad})
    batch = SourceProvider(result, "akshare").fetch_daily_prices("000001.SZ", START, END)
    assert calls == ["stock_zh_a_hist", "stock_zh_a_hist_tx"]
    assert batch.source == "akshare_tx"
    assert batch.records == (bar(day=END),)


def test_scheduler_stale_primary_falls_back_and_dynamic_source_survives_wrappers(tmp_path):
    calendar = SimpleNamespace(days=frozenset({START, END}))
    result, calls = provider(tmp_path, {"stock_zh_a_hist": (bar(day=START),)}, calendar=calendar)
    wrapped = SourceProvider(ReadyProvider(result, calendar), "akshare")
    assert wrapped.fetch_daily_prices("000001.SZ", START, END).source == "akshare_tx"
    assert calls == ["stock_zh_a_hist", "stock_zh_a_hist_tx"]


def test_fixed_primary_and_both_failed_are_visible(tmp_path):
    store = SourcePolicyRepository(str(tmp_path))
    store.save("eastmoney", 0)
    result, calls = provider(tmp_path, {"stock_zh_a_hist": ProviderTimeoutError()})
    with pytest.raises(ProviderTimeoutError):
        result.fetch_daily_prices("000001.SZ", START, END)
    assert calls == ["stock_zh_a_hist"]
    store.save("prefer_eastmoney", 1)
    result, calls = provider(
        tmp_path,
        {"stock_zh_a_hist": ProviderTimeoutError(), "stock_zh_a_hist_tx": ProviderTimeoutError()},
    )
    with pytest.raises(ProviderTimeoutError):
        result.fetch_daily_prices("000001.SZ", START, END)
    assert len(calls) == 2


def test_programming_and_dependency_failures_do_not_switch(tmp_path):
    for error in [
        RuntimeError("fixture defect"),
        ProviderError("provider_dependency_missing", "Missing SDK"),
    ]:
        result, calls = provider(tmp_path, {"stock_zh_a_hist": error})
        with pytest.raises(type(error)):
            result.fetch_daily_prices("000001.SZ", START, END)
        assert calls == ["stock_zh_a_hist"]


@pytest.mark.anyio
async def test_local_authenticated_settings_and_validation(tmp_path):
    app = create_app(Settings(source_policy_directory=str(tmp_path), local_admin_token=TOKEN))
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as client:
        url = "/api/v1/system/source-policy"
        result = await client.get(url)
        assert result.json()["mode"] == "prefer_eastmoney"
        assert TOKEN not in result.text
        payload = {"mode": "tencent", "revision": 0}
        headers = {"Origin": "http://127.0.0.1:5173", "X-Admin-Token": TOKEN}
        assert (
            await client.put(url, json=payload, headers={"Origin": headers["Origin"]})
        ).status_code == 401
        assert (
            await client.put(
                url, json=payload, headers={**headers, "Origin": "https://evil.invalid"}
            )
        ).status_code == 403
        assert (
            await client.put(url, json=payload, headers={**headers, "Host": "evil.invalid"})
        ).status_code == 403
        assert (
            await client.put(url, json=payload, headers={**headers, "Sec-Fetch-Site": "cross-site"})
        ).status_code == 403
        assert (
            await client.put(url, json={**payload, "mode": "arbitrary_url"}, headers=headers)
        ).status_code == 422
        saved = await client.put(url, json=payload, headers=headers)
        assert saved.status_code == 200
        assert saved.json()["mode"] == "tencent"
        assert (await client.put(url, json=payload, headers=headers)).status_code == 409
        fresh = create_app(Settings(source_policy_directory=str(tmp_path)))
        async with AsyncClient(
            transport=ASGITransport(app=fresh), base_url="http://127.0.0.1"
        ) as other:
            assert (await other.get(url)).json()["mode"] == "tencent"


@pytest.mark.anyio
async def test_production_write_disabled_even_with_valid_token(tmp_path):
    app = create_app(
        Settings(
            app_env="production", source_policy_directory=str(tmp_path), local_admin_token=TOKEN
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        response = await client.put(
            "/api/v1/system/source-policy",
            json={"mode": "tencent", "revision": 0},
            headers={"Origin": "http://127.0.0.1:5173", "X-Admin-Token": TOKEN},
        )
        assert response.status_code == 403
        assert SourcePolicyRepository(str(tmp_path)).read().revision == 0
