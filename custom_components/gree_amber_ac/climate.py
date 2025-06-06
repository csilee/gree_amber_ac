"""Support for interface with a Gree Amber climate systems."""

from __future__ import annotations

import logging
from typing import Any

from .greeamberclimate.device import (
    TEMP_MAX,
    TEMP_MAX_F,
    TEMP_MIN,
    TEMP_MIN_F,
    Quiet,
    FanSpeed,
    HorizontalSwing,
    Mode,
    TemperatureUnits,
    VerticalSwing,
)

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    PRESET_AWAY,
    PRESET_BOOST,
    PRESET_ECO,
    PRESET_NONE,
    PRESET_SLEEP,
    QUIET_OFF,
    QUIET_AUTO,
    QUIET_ON,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_WHOLE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DISPATCH_DEVICE_DISCOVERED,
    FAN_MEDIUM_HIGH,
    FAN_MEDIUM_LOW,
    TARGET_TEMPERATURE_STEP,
)
from .coordinator import DeviceDataUpdateCoordinator, GreeAmberConfigEntry
from .entity import GreeAmberEntity

_LOGGER = logging.getLogger(__name__)

HVAC_MODES = {
    Mode.Auto: HVACMode.AUTO,
    Mode.Cool: HVACMode.COOL,
    Mode.Dry: HVACMode.DRY,
    Mode.Fan: HVACMode.FAN_ONLY,
    Mode.Heat: HVACMode.HEAT,
}
HVAC_MODES_REVERSE = {v: k for k, v in HVAC_MODES.items()}

PRESET_MODES = [
    PRESET_ECO,  # Power saving mode
    PRESET_AWAY,  # Steady heat, or 8C mode on gree amber units
    PRESET_BOOST,  # Turbo mode
    PRESET_NONE,  # Default operating mode
    PRESET_SLEEP,  # Sleep mode
]

FAN_MODES = {
    FanSpeed.Auto: FAN_AUTO,
    FanSpeed.Low: FAN_LOW,
    FanSpeed.MediumLow: FAN_MEDIUM_LOW,
    FanSpeed.Medium: FAN_MEDIUM,
    FanSpeed.MediumHigh: FAN_MEDIUM_HIGH,
    FanSpeed.High: FAN_HIGH,
}
FAN_MODES_REVERSE = {v: k for k, v in FAN_MODES.items()}

SWING_MODES = [SWING_OFF, SWING_VERTICAL, SWING_HORIZONTAL, SWING_BOTH]

QUIET_MODES = [QUIET_OFF, QUIET_AUTO, QUIET_ON]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GreeAmberConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Gree Amber HVAC device from a config entry."""

    @callback
    def init_device(coordinator: DeviceDataUpdateCoordinator) -> None:
        """Register the device."""
        async_add_entities([GreeAmberClimateEntity(coordinator)])

    for coordinator in entry.runtime_data.coordinators:
        init_device(coordinator)

    entry.async_on_unload(
        async_dispatcher_connect(hass, DISPATCH_DEVICE_DISCOVERED, init_device)
    )


class GreeAmberClimateEntity(GreeAmberEntity, ClimateEntity):
    """Representation of a Gree Amber HVAC device."""

    _attr_precision = PRECISION_WHOLE
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.QUIET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )
    _attr_target_temperature_step = TARGET_TEMPERATURE_STEP
    _attr_hvac_modes = [*HVAC_MODES_REVERSE, HVACMode.OFF]
    _attr_preset_modes = PRESET_MODES
    _attr_fan_modes = [*FAN_MODES_REVERSE]
    _attr_swing_modes = SWING_MODES
    _attr_quiet_modes = QUIET_MODES
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = TEMP_MIN
    _attr_max_temp = TEMP_MAX

    def __init__(self, coordinator: DeviceDataUpdateCoordinator) -> None:
        """Initialize the Gree Amber device."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.device.device_info.mac

    @property
    def current_temperature(self) -> float:
        """Return the reported current temperature for the device."""
        return self.coordinator.device.current_temperature

    @property
    def target_temperature(self) -> float:
        """Return the target temperature for the device."""
        return self.coordinator.device.target_temperature

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if ATTR_TEMPERATURE not in kwargs:
            raise ValueError(f"Hiányzó paraméter {ATTR_TEMPERATURE}")

        if hvac_mode := kwargs.get(ATTR_HVAC_MODE):
            await self.async_set_hvac_mode(hvac_mode)

        temperature = kwargs[ATTR_TEMPERATURE]
        _LOGGER.debug(
            "Hőmérséklet %d állítva a %s eszközön",
            temperature,
            self._attr_name,
        )

        self.coordinator.device.target_temperature = temperature
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode for the device."""
        if not self.coordinator.device.power:
            return HVACMode.OFF

        return HVAC_MODES.get(self.coordinator.device.mode)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        if hvac_mode not in self.hvac_modes:
            raise ValueError(f"Ismeretlen HVAC mód: {hvac_mode}")

        _LOGGER.debug(
            "HVAC mód %s állítva a %s eszközön",
            hvac_mode,
            self._attr_name,
        )

        if hvac_mode == HVACMode.OFF:
            self.coordinator.device.power = False
            await self.coordinator.push_state_update()
            self.async_write_ha_state()
            return

        if not self.coordinator.device.power:
            self.coordinator.device.power = True

        self.coordinator.device.mode = HVAC_MODES_REVERSE.get(hvac_mode)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn on the device."""
        _LOGGER.debug("HVAC kekapcsolva a %s eszközön", self._attr_name)

        self.coordinator.device.power = True
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn off the device."""
        _LOGGER.debug("HVAC kikapcsolva a %s eszközön", self._attr_name)

        self.coordinator.device.power = False
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode for the device."""
        if self.coordinator.device.steady_heat:
            return PRESET_AWAY
        if self.coordinator.device.power_save:
            return PRESET_ECO
        if self.coordinator.device.sleep:
            return PRESET_SLEEP
        if self.coordinator.device.turbo:
            return PRESET_BOOST
        return PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in PRESET_MODES:
            raise ValueError(f"Ismeretlen preset mode: {preset_mode}")

        _LOGGER.debug(
            "Preset mód %s beállítva a %s eszközön",
            preset_mode,
            self._attr_name,
        )

        self.coordinator.device.steady_heat = False
        self.coordinator.device.power_save = False
        self.coordinator.device.turbo = False
        self.coordinator.device.sleep = False

        if preset_mode == PRESET_AWAY:
            self.coordinator.device.steady_heat = True
        elif preset_mode == PRESET_ECO:
            self.coordinator.device.power_save = True
        elif preset_mode == PRESET_BOOST:
            self.coordinator.device.turbo = True
        elif preset_mode == PRESET_SLEEP:
            self.coordinator.device.sleep = True

        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode for the device."""
        speed = self.coordinator.device.fan_speed
        return FAN_MODES.get(speed)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set new target fan mode."""
        if fan_mode not in FAN_MODES_REVERSE:
            raise ValueError(f"Ismeretlen ventillátormód: {fan_mode}")

        self.coordinator.device.fan_speed = FAN_MODES_REVERSE.get(fan_mode)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()


    @property
    def quiet_mode(self) -> str | None:
        """Return the current quiet mode for the device."""
        quiet = self.coordinator.device.quiet
        return QUIET_MODES.get(quiet)

    async def async_set_quiet_mode(self, quiet_mode: str) -> None:
        """Set new target fan mode."""
        if quiet_mode not in QUIET_MODES:
            raise ValueError(f"Ismeretlen csendesmód: {quiet_mode}")

        self.coordinator.device.quiet = QUIET_MODES.get(quiet_mode)
        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    @property
    def swing_mode(self) -> str:
        """Return the current swing mode for the device."""
        h_swing = self.coordinator.device.horizontal_swing == HorizontalSwing.FullSwing
        v_swing = self.coordinator.device.vertical_swing == VerticalSwing.FullSwing

        if h_swing and v_swing:
            return SWING_BOTH
        if h_swing:
            return SWING_HORIZONTAL
        if v_swing:
            return SWING_VERTICAL
        return SWING_OFF

    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Set new target swing operation."""
        if swing_mode not in SWING_MODES:
            raise ValueError(f"Ismeretlen lenyezőmód: {swing_mode}")

        _LOGGER.debug(
            "Legyezőmód %s állítva az %s eszközön",
            swing_mode,
            self._attr_name,
        )

        self.coordinator.device.horizontal_swing = HorizontalSwing.Center
        self.coordinator.device.vertical_swing = VerticalSwing.FixedMiddle
        if swing_mode in (SWING_BOTH, SWING_HORIZONTAL):
            self.coordinator.device.horizontal_swing = HorizontalSwing.FullSwing
        if swing_mode in (SWING_BOTH, SWING_VERTICAL):
            self.coordinator.device.vertical_swing = VerticalSwing.FullSwing

        await self.coordinator.push_state_update()
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        """Update the state of the entity."""
        units = self.coordinator.device.temperature_units
        if (
            units == TemperatureUnits.C
            and self._attr_temperature_unit != UnitOfTemperature.CELSIUS
        ):
            _LOGGER.debug("Hőmérséklet mértékegység celsiusra állítva")
            self._attr_temperature_unit = UnitOfTemperature.CELSIUS
            self._attr_min_temp = TEMP_MIN
            self._attr_max_temp = TEMP_MAX
        elif (
            units == TemperatureUnits.F
            and self._attr_temperature_unit != UnitOfTemperature.FAHRENHEIT
        ):
            _LOGGER.debug("Hőmérséklet mértékegység fahrenheitre állítva")
            self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
            self._attr_min_temp = TEMP_MIN_F
            self._attr_max_temp = TEMP_MAX_F

        super()._handle_coordinator_update()
