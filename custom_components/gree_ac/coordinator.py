"""Helper and wrapper classes for Gree Amber module."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from .greeamberclimate.device import Device, DeviceInfo
from .greeamberclimate.discovery import Discovery, Listener
from .greeamberclimate.exceptions import DeviceNotBoundError, DeviceTimeoutError
from .greeamberclimate.network import Response

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.dt import utcnow

from .const import (
    DISCOVERY_TIMEOUT,
    DISPATCH_DEVICE_DISCOVERED,
    DOMAIN,
    MAX_ERRORS,
    MAX_EXPECTED_RESPONSE_TIME_INTERVAL,
    UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type GreeAmberConfigEntry = ConfigEntry[GreeAmberRuntimeData]


@dataclass
class GreeAmberRuntimeData:
    """RUntime data for Gree Amber Climate integration."""

    discovery_service: DiscoveryService
    coordinators: list[DeviceDataUpdateCoordinator]


class DeviceDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manages polling for state changes from the device."""

    config_entry: GreeAmberConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: GreeAmberConfigEntry, device: Device
    ) -> None:
        """Initialize the data update coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-{device.device_info.name}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,
        )
        self.device = device
        print(f"Eszköz kezelőhöz adva: {self.device}")
        self.device.add_handler(Response.RESULT, self.device_state_updated)
        print(f"Eszköz kezelőhöz adva: {self.device}")

        self._error_count: int = 0
        self._last_response_time: datetime = utcnow()
        self._last_error_time: datetime | None = None

        _LOGGER.debug(
            "Gree Amber eszköz: %s ekkor %s:%i beállítva",
            self.device.device_info.name,
            self.device.device_info.ip,
            self.device.device_info.port,
        )

    def device_state_updated(self, *args: Any) -> None:
        """Handle device state updates."""
        _LOGGER.debug("Eszköz státusza megváltozott: %s", json_dumps(args))
        self._error_count = 0
        self._last_response_time = utcnow()
        self.async_set_updated_data(self.device.raw_properties)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the state of the device."""
        _LOGGER.debug(
            "Eszköz státusza frissítve: %s, hibaszámláló: %d", self.name, self._error_count
        )
        try:
            await self.device.update_state()
        except DeviceNotBoundError as error:
            raise UpdateFailed(
                f"{self.name} eszköz elérhetettlen, az eszköz nincs jelen."
            ) from error
        except DeviceTimeoutError as error:
            self._error_count += 1

            # Under normal conditions GREE AMBER units timeout every once in a while
            if self.last_update_success and self._error_count >= MAX_ERRORS:
                _LOGGER.warning(
                    "Eszköz %s elérhetettlen: %s", self.name, self.device.device_info
                )
                raise UpdateFailed(
                    f"{self.name} eszköz elérhetettlen, nem sikerült elküldeni a frissítési kérelmet"
                ) from error
        else:
            # raise update failed if time for more than MAX_ERRORS has passed since last update
            now = utcnow()
            elapsed_success = now - self._last_response_time
            if self.update_interval and elapsed_success >= timedelta(
                seconds=MAX_EXPECTED_RESPONSE_TIME_INTERVAL
            ):
                if not self._last_error_time or (
                    (now - self.update_interval) >= self._last_error_time
                ):
                    self._last_error_time = now
                    self._error_count += 1

                _LOGGER.warning(
                    "A(z) %s eszköz szokatlanul sokáig várt a válaszadásra, %s másodperc",
                    self.name,
                    elapsed_success,
                )
            else:
                self._error_count = 0
            if self.last_update_success and self._error_count >= MAX_ERRORS:
                raise UpdateFailed(
                    f"A(z) {self.name} eszköz túl sokáig nem válaszol, és most nem érhető el."
                )

        self._last_response_time = utcnow()
        return copy.deepcopy(self.device.raw_properties)

    async def push_state_update(self):
        """Send state updates to the physical device."""
        try:
            return await self.device.push_state_update()
        except DeviceTimeoutError:
            _LOGGER.warning(
                "Időtúllépés az állapotfrissítés küldésekor ide: %s (%s)",
                self.name,
                self.device.device_info,
            )


class DiscoveryService(Listener):
    """Discovery event handler for gree amber devices."""

    def __init__(self, hass: HomeAssistant, entry: GreeAmberConfigEntry) -> None:
        """Initialize discovery service."""
        super().__init__()
        self.hass = hass
        self.entry = entry

        self.discovery = Discovery(DISCOVERY_TIMEOUT)
        self.discovery.add_listener(self)

    async def device_found(self, device_info: DeviceInfo) -> None:
        """Handle new device found on the network."""

        device = Device(device_info)
        try:
            await device.bind()
        except DeviceNotBoundError:
            _LOGGER.error("Nem sikerült csatlakozni a Gree Amber eszközhöz: %s", device_info)
        except DeviceTimeoutError:
            _LOGGER.error("Időtúllépés a Gree Amber eszközhöz való csatlakozás során: %s", device_info)

        _LOGGER.debug(
            "Gree Amber eszköz hozzáadása %s ekkor %s:%i",
            device.device_info.name,
            device.device_info.ip,
            device.device_info.port,
        )
        print(
            f"Gree Amber eszköz hozzáadása {device.device_info.name} ekkor {device.device_info.ip}:{device.device_info.port}"
        )
        coordo = DeviceDataUpdateCoordinator(self.hass, self.entry, device)
        print(f"Feldolgozó eszköz: {device}")
        self.entry.runtime_data.coordinators.append(coordo)
        print(f"Koordinátorok: {self.entry.runtime_data.coordinators}")
        await coordo.async_refresh()

        async_dispatcher_send(self.hass, DISPATCH_DEVICE_DISCOVERED, coordo)

    async def device_update(self, device_info: DeviceInfo) -> None:
        """Handle updates in device information, update if ip has changed."""
        for coordinator in self.entry.runtime_data.coordinators:
            if coordinator.device.device_info.mac == device_info.mac:
                coordinator.device.device_info.ip = device_info.ip
                await coordinator.async_refresh()
