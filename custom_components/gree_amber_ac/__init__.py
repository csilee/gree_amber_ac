"""The Gree Amber Climate integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import DISCOVERY_SCAN_INTERVAL
from .coordinator import DiscoveryService, GreeAmberConfigEntry, GreeAmberRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: GreeAmberConfigEntry) -> bool:
    """Set up Gree Amber Climate from a config entry."""
    greeamber_discovery = DiscoveryService(hass, entry)
    entry.runtime_data = GreeAmberRuntimeData(
        discovery_service=greeamber_discovery, coordinators=[]
    )

    async def _async_scan_update(_=None):
        bcast_addr = list(await async_get_ipv4_broadcast_addresses(hass))
        await greeamber_discovery.discovery.scan(0, bcast_ifaces=bcast_addr)

    _LOGGER.debug("Gree Amber eszközök keresése a hálózaton")
    await _async_scan_update()

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_update, timedelta(seconds=DISCOVERY_SCAN_INTERVAL)
        )
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GreeAmberConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
