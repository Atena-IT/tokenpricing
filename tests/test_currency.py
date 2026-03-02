from decimal import Decimal

import pytest

import tokenpricing.currency as currency


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_usd_rates_cached(monkeypatch):
    calls = {"count": 0}

    def fake_sync_get_usd_rates():
        calls["count"] += 1
        return {"EUR": Decimal("0.9"), "JPY": Decimal("150")}

    # Ensure clean cache
    currency._get_usd_rates_bucketed.cache_clear()
    monkeypatch.setattr(currency, "_sync_get_usd_rates", fake_sync_get_usd_rates)

    # First call should invoke the sync fetch once
    rates1 = await currency.get_usd_rates(force_refresh=True)
    assert calls["count"] == 1

    # Second call within same TTL bucket should be cached
    rates2 = await currency.get_usd_rates()
    assert calls["count"] == 1
    # Should be the same mapping instance from cache
    assert rates1 is rates2
    assert isinstance(rates2["EUR"], Decimal)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_usd_rate_usd_short_circuit(monkeypatch):
    calls = {"count": 0}

    def fake_sync_get_usd_rates():
        calls["count"] += 1
        return {"EUR": Decimal("0.9")}

    currency._get_usd_rates_bucketed.cache_clear()
    monkeypatch.setattr(currency, "_sync_get_usd_rates", fake_sync_get_usd_rates)

    # Requesting USD should not trigger rates fetch
    r1 = await currency.get_usd_rate("USD")
    r2 = await currency.get_usd_rate("usd")
    assert r1 == Decimal("1") and r2 == Decimal("1")
    assert calls["count"] == 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_usd_rate_cached(monkeypatch):
    calls = {"count": 0}

    def fake_sync_get_usd_rates():
        calls["count"] += 1
        return {"EUR": Decimal("0.9")}

    currency._get_usd_rates_bucketed.cache_clear()
    monkeypatch.setattr(currency, "_sync_get_usd_rates", fake_sync_get_usd_rates)

    # First call should populate cache
    eur1 = await currency.get_usd_rate("EUR")
    assert eur1 == Decimal("0.9")
    assert calls["count"] == 1

    # Second call should use cache (no additional sync calls)
    eur2 = await currency.get_usd_rate("EUR")
    assert eur2 == Decimal("0.9")
    assert calls["count"] == 1
