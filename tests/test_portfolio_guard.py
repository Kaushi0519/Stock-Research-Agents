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


@pytest.mark.parametrize("func_name,args", [
    ("order_buy_market", ("AAPL", 1)),
    ("order_sell_market", ("AAPL", 1)),
    ("order_buy_limit", ("AAPL", 1, 100.0)),
    ("order_buy_fractional_by_price", ("AAPL", 10.0)),
    ("order_buy_crypto_by_price", ("BTC", 10.0)),
    ("order_buy_option_limit", ()),
    ("cancel_all_stock_orders", ()),
    ("order", ()),
])
def test_top_level_write_functions_raise_read_only_violation(func_name, args):
    """`robin_stocks.robinhood` re-exports the order functions at the top
    level, and `rh.order_buy_market(...)` is the usual way to call them -- so
    the top-level names must be blocked too, not just `rh.orders.*`."""
    enforce_read_only()
    import robin_stocks.robinhood as rh

    func = getattr(rh, func_name)
    with pytest.raises(ReadOnlyViolation):
        func(*args)


def test_no_unblocked_write_function_reachable_anywhere_in_package():
    """Exhaustive check: no module in `robin_stocks.robinhood` (top level or
    any submodule) still holds a reference to an original, unpatched
    order/cancel/buy/sell function."""
    import sys

    enforce_read_only()
    import robin_stocks.robinhood as rh

    leaks = []
    for mod_name, module in list(sys.modules.items()):
        if module is None or not (
            mod_name == rh.__name__ or mod_name.startswith(rh.__name__ + ".")
        ):
            continue
        for attr_name, attr in vars(module).items():
            if attr_name.startswith("_") or not callable(attr):
                continue
            if not (attr_name.startswith(("order", "cancel", "buy", "sell"))):
                continue
            if getattr(attr, "__module__", "").startswith(rh.__name__) and not getattr(
                attr, "__blocked_by_guard__", False
            ):
                leaks.append(f"{mod_name}.{attr_name}")

    assert leaks == []


@pytest.mark.parametrize("func_name", [
    "login",
    "build_holdings",
    "get_all_stock_orders",
    "get_crypto_positions",
])
def test_top_level_read_functions_are_not_blocked(func_name):
    enforce_read_only()
    import robin_stocks.robinhood as rh

    func = getattr(rh, func_name)
    assert getattr(func, "__blocked_by_guard__", False) is False


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
