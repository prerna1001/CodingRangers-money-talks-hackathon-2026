from __future__ import annotations


def decompose(prior_qty: float, prior_price: float, current_qty: float, current_price: float) -> dict[str, float]:
    prior_revenue = prior_qty * prior_price
    current_revenue = current_qty * current_price
    volume = (current_qty - prior_qty) * prior_price
    price = (current_price - prior_price) * prior_qty
    mix = (current_qty - prior_qty) * (current_price - prior_price)
    return {
        "prior_revenue": round(prior_revenue, 2),
        "volume": round(volume, 2),
        "price": round(price, 2),
        "mix": round(mix, 2),
        "current_revenue": round(current_revenue, 2),
        "delta": round(current_revenue - prior_revenue, 2),
    }

