"""Config flow for Gree Amber."""

from .greeamberclimate.discovery import Discovery

from homeassistant.components.network import async_get_ipv4_broadcast_addresses
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .const import DISCOVERY_TIMEOUT, DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Return if there are devices that can be discovered."""
    greeamber_discovery = Discovery(DISCOVERY_TIMEOUT)
    bcast_addr = list(await async_get_ipv4_broadcast_addresses(hass))
    devices = await greeamber_discovery.scan(
        wait_for=DISCOVERY_TIMEOUT, bcast_ifaces=bcast_addr
    )
    return len(devices) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "Gree Amber Climate", _async_has_devices)
