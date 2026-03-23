"""Shared test fixtures and mock helpers for StatusPage Monitor tests."""
from __future__ import annotations

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Polyfill asyncio.timeout for Python < 3.11
# ---------------------------------------------------------------------------
if not hasattr(asyncio, "timeout"):
    from contextlib import asynccontextmanager as _acm

    @_acm
    async def _timeout(delay):
        yield

    asyncio.timeout = _timeout

# ---------------------------------------------------------------------------
# Stub out homeassistant modules so provider imports work without HA installed.
# Only the providers themselves are tested here; they don't use HA at runtime.
# ---------------------------------------------------------------------------
_HA_STUBS = [
    "homeassistant",
    "homeassistant.components",
    "homeassistant.components.http",
    "homeassistant.components.sensor",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.helpers.entity_registry",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.util",
    "homeassistant.data_entry_flow",
    "voluptuous",
]
for _mod in _HA_STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


class MockResponse:
    """Minimal aiohttp response mock supporting async context manager."""

    def __init__(self, data: Any = None, status: int = 200, text: str = ""):
        self.status = status
        self._data = data
        self._text = text

    async def json(self, *, content_type=None):
        return self._data

    async def text(self):
        return self._text if self._text else json.dumps(self._data or {})

    def raise_for_status(self):
        if self.status >= 400:
            from aiohttp import ClientResponseError, RequestInfo
            from yarl import URL

            raise ClientResponseError(
                request_info=RequestInfo(URL("http://test"), "GET", MagicMock(), URL("http://test")),
                history=(),
                status=self.status,
            )

    def __await__(self):
        """Allow ``await session.get(...)`` (used in asyncio.gather)."""
        return self._await_impl().__await__()

    async def _await_impl(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class MockSession:
    """Mock aiohttp.ClientSession that returns predefined responses per URL.

    Usage::

        session = MockSession({
            "https://example.com/api": MockResponse({"key": "value"}),
            "https://example.com/fail": MockResponse(status=404),
        })
    """

    def __init__(self, responses: dict[str, MockResponse] | None = None):
        self._responses = responses or {}

    def get(self, url: str, **kwargs) -> MockResponse:
        # Match by URL prefix to handle query strings.
        for pattern, response in self._responses.items():
            if url == pattern or url.startswith(pattern + "?"):
                return response
        return MockResponse(status=404)


@pytest.fixture
def mock_session():
    """Return a factory that creates a MockSession from a response dict."""
    def _factory(responses: dict[str, MockResponse]) -> MockSession:
        return MockSession(responses)
    return _factory
