from cart import total


def test_empty_cart():
    assert total([]) == 0.0


def test_single_item():
    assert total([10.0]) == 10.0


def test_plain_sum():
    assert total([1.0, 2.0, 3.5]) == 6.5


def test_bulk_discount_at_five_items():
    # 5 or more items get 10% off
    assert total([20.0] * 5) == 90.0


def test_no_discount_below_five_items():
    assert total([25.0] * 4) == 100.0


def test_cents_rounding():
    assert total([0.1, 0.2]) == 0.3
