from __future__ import annotations

from analytics.price_volume_mix import decompose


def test_price_volume_mix_identity_sum() -> None:
    result = decompose(prior_qty=10, prior_price=100, current_qty=12, current_price=110)
    assert result["volume"] + result["price"] + result["mix"] == result["delta"]
    assert result["current_revenue"] - result["prior_revenue"] == result["delta"]

