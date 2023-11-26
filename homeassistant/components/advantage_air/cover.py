"""Cover platform for Advantage Air integration."""
from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ADVANTAGE_AIR_STATE_CLOSE,
    ADVANTAGE_AIR_STATE_OPEN,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)
from .entity import AdvantageAirThingEntity, AdvantageAirZoneEntity
from .models import AdvantageAirData

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    instance: AdvantageAirData = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]

    entities: list[CoverEntity] = []
    entities.extend(setup_zone_vent_controls(instance))
    entities.extend(setup_thing_covers(instance))

    async_add_entities(entities)


def setup_zone_vent_controls(instance: AdvantageAirData) -> List[CoverEntity]:
    return [
        AdvantageAirZoneVent(instance, ac_key, zone_key)
        for ac_key, ac_device in instance.coordinator.data.get("aircons", {}).items()
        for zone_key, zone in ac_device.get("zones", {}).items()
        if zone["type"] == 0
    ]


def setup_thing_covers(instance: AdvantageAirData) -> List[CoverEntity]:
    def is_blind(thing):
        return thing["channelDipState"] in [1, 2]

    def is_garage_door(thing):
        return thing["channelDipState"] == 3

    blind_covers = [
        AdvantageAirThingCover(instance, thing, CoverDeviceClass.BLIND)
        for thing in instance.coordinator.data.get("myThings", {}).get("things", {}).values()
        if is_blind(thing)
    ]

    garage_door_covers = [
        AdvantageAirThingCover(instance, thing, CoverDeviceClass.GARAGE)
        for thing in instance.coordinator.data.get("myThings", {}).get("things", {}).values()
        if is_garage_door(thing)
    ]

    return blind_covers + garage_door_covers



class AdvantageAirZoneVent(AdvantageAirZoneEntity, CoverEntity):
    """Advantage Air Zone Vent."""

    _attr_device_class = CoverDeviceClass.DAMPER
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, instance: AdvantageAirData, ac_key: str, zone_key: str) -> None:
        """Initialize an Advantage Air Zone Vent."""
        super().__init__(instance, ac_key, zone_key)
        self._attr_name = self._zone["name"]

    @property
    def is_closed(self) -> bool:
        """Return if vent is fully closed."""
        return self._zone["state"] == ADVANTAGE_AIR_STATE_CLOSE

    @property
    def current_cover_position(self) -> int:
        """Return vents current position as a percentage."""
        if self._zone["state"] == ADVANTAGE_AIR_STATE_OPEN:
            return self._zone["value"]
        return 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Fully open zone vent."""
        await self.async_update_zone(
            {"state": ADVANTAGE_AIR_STATE_OPEN, "value": 100},
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Fully close zone vent."""
        await self.async_update_zone({"state": ADVANTAGE_AIR_STATE_CLOSE})

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Change vent position."""
        position = round(kwargs[ATTR_POSITION] / 5) * 5
        if position == 0:
            await self.async_update_zone({"state": ADVANTAGE_AIR_STATE_CLOSE})
        else:
            await self.async_update_zone(
                {
                    "state": ADVANTAGE_AIR_STATE_OPEN,
                    "value": position,
                }
            )


class AdvantageAirThingCover(AdvantageAirThingEntity, CoverEntity):
    """Representation of Advantage Air Cover controlled by MyPlace."""

    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        instance: AdvantageAirData,
        thing: dict[str, Any],
        device_class: CoverDeviceClass,
    ) -> None:
        """Initialize an Advantage Air Things Cover."""
        super().__init__(instance, thing)
        self._attr_device_class = device_class

    @property
    def is_closed(self) -> bool:
        """Return if cover is fully closed."""
        return self._data["value"] == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Fully open zone vent."""
        return await self.async_turn_on()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Fully close zone vent."""
        return await self.async_turn_off()
