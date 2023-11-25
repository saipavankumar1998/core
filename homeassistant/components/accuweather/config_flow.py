"""Adds config flow for AccuWeather."""
from __future__ import annotations

import asyncio
from asyncio import timeout
from typing import Any

from accuweather import AccuWeather, ApiError, InvalidApiKeyError, RequestsExceededError
from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_CITY, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaFlowFormStep,
    SchemaOptionsFlowHandler,
)

from .const import CONF_FORECAST, DOMAIN

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_FORECAST, default=False): bool,
    }
)
OPTIONS_FLOW = {
    "init": SchemaFlowFormStep(OPTIONS_SCHEMA),
}


class AccuWeatherFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for AccuWeather."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        # Under the terms of use of the API, one user can use one free API key. Due to
        # the small number of requests allowed, we only allow one integration instance.
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors = {}

        if user_input is not None:
            websession = async_get_clientsession(self.hass)
            try:
                async with timeout(20):
                    # Get the location key by querying for the city
                    city = user_input[CONF_CITY]
                    url1 = f"http://dataservice.accuweather.com/locations/v1/cities/search?apikey={user_input[CONF_API_KEY]}&q={city}"
                    location_key_request = await websession.get(url1)
                    location_key_response = await location_key_request.json()
                    location_key = location_key_response[0]["Key"]

                    # Get the lat and long from the location_key
                    url2 = f"http://dataservice.accuweather.com/locations/v1/{location_key}?apikey={user_input[CONF_API_KEY]}"
                    lat_long_request = await websession.get(url2)
                    lat_long_response = await lat_long_request.json()
                    latitude = lat_long_response["GeoPosition"]["Latitude"]
                    longitude = lat_long_response["GeoPosition"]["Longitude"]

                    # Use the location key to fetch the weather data
                    accuweather = AccuWeather(
                        user_input[CONF_API_KEY],
                        websession,
                        latitude=latitude,
                        longitude=longitude,
                    )
                    await accuweather.async_get_location()
            except (ApiError, ClientConnectorError, asyncio.TimeoutError, ClientError):
                errors["base"] = "cannot_connect"
            except InvalidApiKeyError:
                errors[CONF_API_KEY] = "invalid_api_key"
            except RequestsExceededError:
                errors[CONF_API_KEY] = "requests_exceeded"
            else:
                await self.async_set_unique_id(
                    accuweather.location_key, raise_on_progress=False
                )

            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_CITY, default=self.hass.config.city): str,
                    vol.Optional(
                        CONF_NAME, default=self.hass.config.location_name
                    ): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SchemaOptionsFlowHandler:
        """Options callback for AccuWeather."""
        return SchemaOptionsFlowHandler(config_entry, OPTIONS_FLOW)
