"""Pytest configuration and marker-driven skip logic."""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    del config
    api_key = os.getenv("INTEGRATION_API_KEY", "").strip()
    if api_key:
        return

    skip_no_key = pytest.mark.skip(reason="INTEGRATION_API_KEY is not set")
    for item in items:
        if "requires_integration_api_key" in item.keywords:
            item.add_marker(skip_no_key)
