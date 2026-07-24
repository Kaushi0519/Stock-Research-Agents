import pytest

from src.portfolio.guard import ReadOnlyViolation, enforce_read_only


def test_enforce_read_only_patches_at_least_one_function():
    # Idempotent, so this just confirms the guard has (already) run and
    # found real functions to neuter -- not that it patches on *this* call
    # specifically, since other tests/modules may have triggered it first.
    enforce_read_only()

    import robin_stocks.robinhood as rh

    assert getattr(rh.orders.order_buy_market, "__blocked_by_guard__", False) is True


@pytest.mark.parametrize("func_name,args", [
    ("order_buy_market", ("AAPL", 1)),
    ("order_sell_market", ("AAPL", 1)),
    ("order_buy_limit", ("AAPL", 1, 100.0)),
    ("order_sell_limit", ("AAPL", 1, 100.0)),
    ("cancel_all_stock_orders", ()),
    ("cancel_all_option_orders", ()),
    ("cancel_all_crypto_orders", ()),
    ("cancel_stock_order", ("some-order-id",)),
    ("order", ()),
])
def test_write_functions_raise_read_only_violation(func_name, args):
    enforce_read_only()
    import robin_stocks.robinhood as rh

    func = getattr(rh.orders, func_name)
    with pytest.raises(ReadOnlyViolation):
        func(*args)


@pytest.mark.parametrize("func_name", [
    "get_all_stock_orders",
    "get_all_open_stock_orders",
    "get_crypto_positions",
    "get_stock_order_info",
])
def test_read_functions_are_not_blocked(func_name):
    """Read functions must remain the real, callable functions -- verified
    without actually calling them (that would hit the network)."""
    enforce_read_only()
    import robin_stocks.robinhood as rh

    func = getattr(rh.orders, func_name)
    assert getattr(func, "__blocked_by_guard__", False) is False
