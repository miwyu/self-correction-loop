"""Shopping-cart total with quantity discounts (v2, tier-table rewrite)."""

DISCOUNT_TIERS = [(5, 0.10)]  # (min_items, rate) — largest qualifying tier wins


def _discount_rate(count):
    rate = 0.0
    for min_items, tier_rate in DISCOUNT_TIERS:
        if count >= min_items:
            rate = tier_rate
    return rate


def total(items):
    subtotal = sum(items)
    subtotal -= subtotal * _discount_rate(len(items))
    return subtotal
