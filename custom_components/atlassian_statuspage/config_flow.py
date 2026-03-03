"""Config flow for Atlassian Statuspage integration."""
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
    API_SUMMARY_PATH,
    API_TIMEOUT,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)
from .coordinator import validate_statuspage_url

_LOGGER = logging.getLogger(__name__)


async def _fetch_page_info(hass, url: str) -> dict:
    """Fetch the summary JSON and return page metadata.

    Raises aiohttp.ClientError or asyncio.TimeoutError on failure.
    """
    api_url = f"{url}{API_SUMMARY_PATH}"
    session = async_get_clientsession(hass)
    async with asyncio.timeout(API_TIMEOUT):
        async with session.get(api_url, headers={"Accept": "application/json"}) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)
    return data


class StatuspageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atlassian Statuspage.

    Each config entry represents one status page URL.  Multiple entries can
    be created to monitor several status pages simultaneously.
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
                url = validate_statuspage_url(raw_url)
            except ValueError as err:
                errors[CONF_URL] = "invalid_url"
                description_placeholders["error_detail"] = str(err)
            else:
                try:
                    data = await _fetch_page_info(self.hass, url)
                except asyncio.TimeoutError:
                    errors["base"] = "timeout"
                except aiohttp.ClientResponseError as err:
                    if err.status == 404:
                        errors[CONF_URL] = "not_a_statuspage"
                    else:
                        errors["base"] = "cannot_connect"
                    _LOGGER.debug("HTTP error during config flow validation: %s", err)
                except aiohttp.ClientError:
                    errors["base"] = "cannot_connect"
                except Exception:  # noqa: BLE001
                    _LOGGER.exception("Unexpected error during config flow validation")
                    errors["base"] = "unknown"
                else:
                    page_name = data.get("page", {}).get("name") or url
                    # Prevent duplicate entries for the same URL
                    await self.async_set_unique_id(url.lower())
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=page_name,
                        data={
                            CONF_URL: url,
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
    def async_get_options_flow(config_entry: ConfigEntry) -> StatuspageOptionsFlow:
        """Return the options flow so users can adjust the poll interval."""
        return StatuspageOptionsFlow(config_entry)


class StatuspageOptionsFlow(OptionsFlow):
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
