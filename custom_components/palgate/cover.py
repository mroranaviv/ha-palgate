"""Sensor file for Palgate."""

from typing import Any, Optional

from homeassistant.components.cover import (
    CoverEntity,
    CoverEntityDescription,
    CoverDeviceClass,
)
from homeassistant.helpers.entity import Entity

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import PalgateApiClient
from .const import DOMAIN as PALGATE_DOMAIN
from .const import *

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Palgate entities from a config_entry."""

    # a ‘hub’ device represents the phone number that links all gates
    HUB_IDENT = (PALGATE_DOMAIN, entry.data[CONF_PHONE_NUMBER])

    # first, register the hub itself so things can be attached to it
    async_add_entities([PalgateHub(entry.data[CONF_PHONE_NUMBER])])

    # gather list of gate ids (migrated entries may only have single DEVICE_ID)
    device_ids: list[str] = entry.data.get(CONF_DEVICE_IDS) or [
        entry.data[CONF_DEVICE_ID]
    ]

    covers = []
    for dev_id in device_ids:
        description = CoverEntityDescription(
            key=dev_id,
            name=dev_id,
            icon="mdi:boom-gate-outline",
            device_class=CoverDeviceClass.GARAGE,
        )

        api = PalgateApiClient(
            device_id=dev_id,
            token=entry.data[CONF_TOKEN],
            token_type=entry.data[CONF_TOKEN_TYPE],
            phone_number=entry.data[CONF_PHONE_NUMBER],
            seconds_to_open=entry.data[CONF_ADVANCED][CONF_SECONDS_TO_OPEN],
            seconds_open=entry.data[CONF_ADVANCED][CONF_SECONDS_OPEN],
            seconds_to_close=entry.data[CONF_ADVANCED][CONF_SECONDS_TO_CLOSE],
            allow_invert_as_stop=entry.data[CONF_ADVANCED][CONF_ALLOW_INVERT_AS_STOP],
            session=async_get_clientsession(hass),
        )

        covers.append(PalgateCover(api, description, hub_ident=HUB_IDENT))

    async_add_entities(covers)


class PalgateHub(Entity):
    """Dummy entity used to represent a phone‑number hub.

    This entity never exposes any real controls; it simply exists so that
    other gate entities can set ``via_device`` to it and get grouped under
    the same tile on the Devices page.
    """

    def __init__(self, phone_number: str) -> None:
        self._attr_unique_id = f"hub_{phone_number}"
        self._attr_device_info = DeviceInfo(
            identifiers={(PALGATE_DOMAIN, phone_number)},
            name=f"Palgate {phone_number}",
            manufacturer="Palgate",
            model="Hub",
        )

    # we do not implement any of the cover logic – this entity is inert


class PalgateCover(CoverEntity):
    """Define a Palgate entity."""

    def __init__(
        self,
        api: PalgateApiClient,
        description: CoverEntityDescription,
        hub_ident,
    ) -> None:
        """Initialize."""

        self.api = api
        self.entity_description = description

        self._attr_unique_id = f"{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(PALGATE_DOMAIN, description.key)},
            name="Palgate",
            model="Palgate",
            manufacturer="Palgate",
            via_device=hub_ident,
        )

    @property
    def is_opening(self) -> Optional[bool]:
        """Return if the cover is opening or not."""
        return self.api.is_opening()

    @property
    def is_closing(self) -> Optional[bool]:
        """Return if the cover is closing or not."""
        return self.api.is_closing()

    @property
    def is_closed(self) -> Optional[bool]:
        """Return if the cover is closed or not."""
        return self.api.is_closed()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""

        await self.api.open_gate()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover - only if allowed in config (usually auto-close)"""

        await self.api.invert_gate()