import inspect

import pytest

UI_MARKERS = ("run_test", "asyncio.run")


def _starts_application(function) -> bool:
    try:
        source = inspect.getsource(function)
    except (OSError, TypeError):
        return False
    return any(marker in source for marker in UI_MARKERS)


def pytest_collection_modifyitems(items):
    """Mark tests that start an application, so ``-m "not ui"`` runs only the quick ones."""
    for item in items:
        function = getattr(item, "function", None)
        if function is not None and _starts_application(function):
            item.add_marker(pytest.mark.ui)
