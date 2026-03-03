"""Config flow for Status Page Monitor."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    API_TIMEOUT,
    CONF_PROVIDER,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import validate_url
from .providers import detect_provider

_LOGGER = logging.getLogger(__name__)


class StatusPageMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Status Page Monitor.

    Each config entry represents one status page URL.  The provider platform
    is auto-detected during setup – no extra step is shown to the user.
    Multiple entries can be created to monitor several status pages at once.
    """

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step where the user enters the status page URL."""
        errors: dict[str, str] = {}
        description_placeholders: dict[str, str] = {}

        if user_input is not None:
            raw_url = user_input.get(CONF_URL, "")
            try:
                url = validate_url(raw_url)
            except ValueError as err:
                errors[CONF_URL] = "invalid_url"
                description_placeholders["error_detail"] = str(err)
            else:
                session = async_get_clientsession(self.hass)
                try:
                    provider = await detect_provider(session, url, API_TIMEOUT)
                except asyncio.TimeoutError:
                    errors["base"] = "timeout"
                    provider = None
                except aiohttp.ClientError:
                    errors["base"] = "cannot_connect"
                    provider = None
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error during provider detection")
                    errors["base"] = "unknown"
                    provider = None

                if provider is None and not errors:
                    errors[CONF_URL] = "not_a_statuspage"

                if not errors and provider is not None:
                    # Fetch the page name for the config entry title
                    try:
                        data = await provider.fetch(session, url, API_TIMEOUT)
                        page_name = data.page.name
                    except Exception:  # noqa: BLE001
                        page_name = url

                    await self.async_set_unique_id(url.lower())
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=page_name,
                        data={
                            CONF_URL: url,
                            CONF_PROVIDER: provider.ID,
                            CONF_SCAN_INTERVAL: user_input.get(
                                CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                            ),
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> StatusPageMonitorOptionsFlow:
        """Return the options flow so users can adjust the poll interval."""
        return StatusPageMonitorOptionsFlow(config_entry)


class StatusPageMonitorOptionsFlow(OptionsFlow):
    """Options flow to adjust settings after initial setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self._config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )

        schema = vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
