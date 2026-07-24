"""Enforces read-only access to Robinhood in code, not just by convention.

At import time, `enforce_read_only()` monkey-patches every function in
`robin_stocks.robinhood` whose name matches a write/order/cancel pattern --
across the `orders`, `options`, and `crypto` submodules -- replacing each
with a stub that raises `ReadOnlyViolation` instead of calling Robinhood's
API. This means a coding mistake anywhere in this project that calls an
order-placing function fails loudly and immediately, instead of silently
placing a real trade.

Design choice: the pattern is deliberately broad (verified empirically
against the installed robin_stocks version -- see DECISIONS.md) and may
also neuter a few harmless helper functions (e.g. `cancel_url`, which just
builds a URL string). That's an accepted trade-off: a blocked read-only
helper is a loud, obvious bug to fix; a missed write function is not.
"""

import re

_WRITE_ACTION_PATTERN = re.compile(r"^(order|cancel|buy|sell)", re.IGNORECASE)
_GUARDED_SUBMODULES = ["orders", "options", "crypto"]

_patched = False


class ReadOnlyViolation(RuntimeError):
    """Raised when code attempts a Robinhood write/order/cancel operation.

    This should never happen in normal operation -- trade execution in this
    project is always manual. If you see this exception, something tried to
    place or cancel a real trade programmatically.
    """


def _blocked(qualified_name: str):
    def _raise(*args, **kwargs):
        raise ReadOnlyViolation(
            f"Blocked call to robin_stocks function '{qualified_name}' -- "
            f"this project enforces read-only Robinhood access at the code "
            f"level. Trade execution must always be manual."
        )

    # Marker attribute so tests (and any future introspection) can confirm
    # a given function was actually neutered, without having to call it.
    _raise.__blocked_by_guard__ = True
    return _raise


def enforce_read_only() -> int:
    """Patch every matching write function. Returns the number patched.

    Idempotent -- calling this more than once (e.g. because multiple
    modules import this file) is a no-op after the first call.
    """
    global _patched
    if _patched:
        return 0

    import robin_stocks.robinhood as rh

    patched_count = 0
    for submodule_name in _GUARDED_SUBMODULES:
        submodule = getattr(rh, submodule_name, None)
        if submodule is None:
            continue

        for attr_name in dir(submodule):
            if attr_name.startswith("_"):
                continue
            if not _WRITE_ACTION_PATTERN.match(attr_name):
                continue

            attr = getattr(submodule, attr_name)
            if not callable(attr):
                continue

            setattr(submodule, attr_name, _blocked(f"{submodule_name}.{attr_name}"))
            patched_count += 1

    _patched = True
    return patched_count
