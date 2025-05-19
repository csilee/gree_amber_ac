import asyncio
import enum
import logging
import re
from asyncio import AbstractEventLoop
from enum import IntEnum, unique
from typing import Union

from .cipher import CipherV1, CipherV2
from .deviceinfo import DeviceInfo
from .exceptions import DeviceNotBoundError, DeviceTimeoutError
from .network import DeviceProtocol2
from .taskable import Taskable


class Props(enum.Enum):
    POWER = "Pow"
    MODE = "Mod"

    # Dehumidifier fields
    HUM_SET = "Dwet"
    HUM_SENSOR = "DwatSen"
    CLEAN_FILTER = "Dfltr"
    WATER_FULL = "DwatFul"
    DEHUMIDIFIER_MODE = "Dmod"

    TEMP_SET = "SetTem"
    TEMP_SENSOR = "TemSen"
    TEMP_UNIT = "TemUn"
    TEMP_BIT = "TemRec"
    FAN_SPEED = "WdSpd"
    FRESH_AIR = "Air"
    XFAN = "Blo"
    ANION = "Health"
    SLEEP = "SwhSlp"
    SLEEP_MODE = "SlpMod"
    LIGHT = "Lig"
    SWING_HORIZ = "SwingLfRig"
    SWING_VERT = "SwUpDn"
    QUIET = "Quiet"
    TURBO = "Tur"
    STEADY_HEAT = "StHt"
    POWER_SAVE = "SvSt"
    UNKNOWN_HEATCOOLTYPE = "HeatCoolType"


@unique
class TemperatureUnits(IntEnum):
    C = 0
    F = 1


@unique
class Mode(IntEnum):
    Auto = 0
    Cool = 1
    Dry = 2
    Fan = 3
    Heat = 4


@unique
class Quiet(IntEnum):
    Off = 0
    Auto = 1
    On = 2


@unique
class FanSpeed(IntEnum):
    Auto = 0
    Low = 1
    MediumLow = 2
    Medium = 3
    MediumHigh = 4
    High = 5


@unique
class HorizontalSwing(IntEnum):
    Default = 0
    FullSwing = 1
    Left = 2
    LeftCenter = 3
    Center = 4
    RightCenter = 5
    Right = 6


@unique
class VerticalSwing(IntEnum):
    Default = 0
    FullSwing = 1
    FixedUpper = 2
    FixedUpperMiddle = 3
    FixedMiddle = 4
    FixedLowerMiddle = 5
    FixedLower = 6
    SwingUpper = 7
    SwingUpperMiddle = 8
    SwingMiddle = 9
    SwingLowerMiddle = 10
    SwingLower = 11


class DehumidifierMode(IntEnum):
    Default = 0
    AnionOnly = 9


def generate_temperature_record(temp_f):
    temSet = round((temp_f - 32.0) * 5.0 / 9.0)
    temRec = (int)((((temp_f - 32.0) * 5.0 / 9.0) - temSet) > 0)
    return {"f": temp_f, "temSet": temSet, "temRec": temRec}


TEMP_MIN = 8
TEMP_MAX = 30
TEMP_OFFSET = 40
TEMP_MIN_F = 46
TEMP_MAX_F = 86
TEMP_MIN_TABLE = -60
TEMP_MAX_TABLE = 60
TEMP_MIN_TABLE_F = -76
TEMP_MAX_TABLE_F = 140
TEMP_TABLE = [
    generate_temperature_record(x)
    for x in range(TEMP_MIN_TABLE_F, TEMP_MAX_TABLE_F + 1)
]
HUMIDITY_MIN = 30
HUMIDITY_MAX = 80


class Device(DeviceProtocol2, Taskable):
    """Egy fizikai eszközt, annak állapotát és tulajdonságait reprezentáló osztály.

    Az eszközöket kötni kell, akár jelenlétük felderítésével, akár egy állandó eszközkulcs megadásával, 
    amelyet aztán az egységgel való kommunikációhoz (és titkosításhoz) használnak. 
    További részletekért lásd a `bind` függvényt.
    
    Miután egy eszköz kötve van, időnként meghívja az `update_state` függvényt, 
    hogy állapotot kérjen le a HVAC-tól és frissítse azt, mivel lehetséges, 
    hogy más forrásokból is megváltoztatja az állapotát.
    
    Attribútumok:
        power: Logikai érték, amely jelzi, hogy az egység be- vagy kikapcsolt állapotban van-e.
        mode: Egész érték, amely az üzemmódot jelzi, a lehetséges értékeket lásd a `Mode` felsorolásban.
        target_temperature: A célhőmérséklet, figyelmen kívül hagyandó, ha Auto, Fan vagy Steady Heat módban van.
        temperature_units: Egész érték, amely a mértékegységet jelzi, a lehetséges értékeket lásd a `TemperatureUnits` felsorolásban.
        current_temperature: Az aktuális hőmérséklet.
        fan_speed: Egész érték, amely a ventilátor sebességét jelzi, a lehetséges értékeket lásd a `FanSpeed` felsorolásban.
        fresh_air: Logikai érték, amely jelzi, hogy a frisslevegő-szelep nyitva van-e, ha van ilyen.
        xfan: Logikai érték, amely engedélyezi a ventilátor számára a tekercs szárítását, csak hűtési és szárítási módokban használatos.
        anion: Logikai érték az ózongenerátor engedélyezéséhez, ha van ilyen.
        sleep: Logikai érték az alvó üzemmód engedélyezéséhez, amely idővel állítja a hőmérsékletet.
        light: Logikai érték az egység világításának engedélyezéséhez, ha van ilyen.
        horizontal_swing: Egész érték, amely a vízszintes lamellák helyzetét szabályozza, a lehetséges értékeket lásd a `HorizontalSwing` felsorolásban.
        vertical_swing: Egész érték A függőleges lapát pozíciójának szabályozásához lásd a `VerticalSwing` felsorolást a lehetséges értékekért.
        quiet: Egész érték a csendes fokozatot jelzi, a lehetséges értékeket lásd a `Quiet` felsorolásban.
        turbo: Logikai érték a turbó működés engedélyezéséhez (kezdetben gyorsabb fűtés vagy hűtés).
        steady_heat: Engedélyezés esetén az egység 8 Celsius fokon tartja a célhőmérsékletet.
        power_save: Logikai érték az energiatakarékos működés engedélyezéséhez.
        target_humidity: Egész érték a cél relatív páratartalom beállításához.
        current_humidity: Az aktuális relatív páratartalom.
        clean_filter: Logikai érték a szűrő tisztításának szükségességére vonatkozóan.
        water_full: Logikai érték a víztartály telítettségére vonatkozóan.
    """

    def __init__(
        self,
        device_info: DeviceInfo,
        timeout: int = 120,
        bind_timeout: int = 10,
        loop: AbstractEventLoop = None,
    ):
        """Initialize the device object

        Args:
            device_info (DeviceInfo): Information about the physical device
            timeout (int): Timeout for device communication
            bind_timeout (int): Timeout for binding to the device, keep this short to prevent delays determining the
                                correct device cipher to use
            loop (AbstractEventLoop): The event loop to run the device operations on
        """
        DeviceProtocol2.__init__(self, timeout)
        Taskable.__init__(self, loop)
        self._logger = logging.getLogger(__name__)
        self.device_info: DeviceInfo = device_info

        self._bind_timeout = bind_timeout

        """ Device properties """
        self.hid = None
        self.version = None
        self.check_version = True
        self._properties = {}
        self._dirty = []
        self._beep = False

    async def bind(
        self,
        key: str = None,
        cipher: Union[CipherV1, CipherV2, None] = None,
    ):
        """Run the binding procedure.

        Binding is a finicky procedure, and happens in 1 of 2 ways:
            1 - Without the key, binding must pass the device info structure immediately following
                the search devices procedure. There is only a small window to complete registration.
            2 - With a key, binding is implicit and no further action is required

            Both approaches result in a device_key which is used as like a persistent session id.

        Args:
            cipher (CipherV1 | CipherV2): The cipher type to use for encryption, if None will attempt to detect the correct one
            key (str): The device key, when provided binding is a NOOP, if None binding will
                       attempt to negotiate the key with the device. cipher must be provided.

        Raises:
            DeviceNotBoundError: If binding was unsuccessful and no key returned
            DeviceTimeoutError: The device didn't respond
        """

        if key:
            if not cipher:
                raise ValueError("a kulcs megadásakor meg kell adni a rejtjelet")
            else:
                cipher.key = key
                self.device_cipher = cipher
                return

        if not self.device_info:
            raise DeviceNotBoundError

        if self._transport is None:
            self._transport, _ = await self._loop.create_datagram_endpoint(
                lambda: self, remote_addr=(self.device_info.ip, self.device_info.port)
            )

        self._logger.info("Eszközkötés indítása ehhez: %s", str(self.device_info))

        try:
            if cipher is not None:
                await self.__bind_internal(cipher)
            else:
                """ Try binding with CipherV1 first, if that fails try CipherV2"""
                try:
                    self._logger.info("Eszközhöz való csatlakozási kísérlet CipherV1 használatával")
                    await self.__bind_internal(CipherV1())
                except asyncio.TimeoutError:
                    self._logger.info("Eszközhöz való csatlakozási kísérlet CipherV2 használatával")
                    await self.__bind_internal(CipherV2())

        except asyncio.TimeoutError:
            raise DeviceTimeoutError

        if not self.device_cipher:
            raise DeviceNotBoundError
        else:
            self._logger.info("Eszközhöz kötve a(z) %s kulcs használatával", self.device_cipher.key)

    async def __bind_internal(self, cipher: Union[CipherV1, CipherV2]):
        """Internal binding procedure, do not call directly"""
        await self.send(self.create_bind_message(self.device_info), cipher=cipher)
        task = asyncio.create_task(self.ready.wait())
        await asyncio.wait_for(task, timeout=self._bind_timeout)

    def handle_device_bound(self, key: str) -> None:
        """Handle the device bound message from the device"""
        self.device_cipher.key = key

    async def request_version(self) -> None:
        """Request the firmware version from the device."""
        if not self.device_cipher:
            await self.bind()

        try:
            await self.send(self.create_status_message(self.device_info, "hid"))

        except asyncio.TimeoutError:
            raise DeviceTimeoutError

    async def update_state(self, wait_for: float = 30):
        """Update the internal state of the device structure of the physical device, 0 for no wait

        Args:
            wait_for (object): How long to wait for an update from the device
        """
        if not self.device_cipher:
            await self.bind()

        self._logger.debug("Eszköztulajdonságok frissítése ehhez: (%s)", str(self.device_info))

        props = [x.value for x in Props]
        if not self.hid:
            props.append("hid")

        try:
            await self.send(self.create_status_message(self.device_info, *props))

        except asyncio.TimeoutError:
            raise DeviceTimeoutError

    def handle_state_update(self, **kwargs) -> None:
        """Handle incoming information about the firmware version of the device"""

        # Ex: hid = 362001000762+U-CS532AE(LT)V3.31.bin
        if "hid" in kwargs:
            self.hid = kwargs.pop("hid")
            match = re.search(r"(?<=V)([\d.]+)\.bin$", self.hid)
            self.version = match and match.group(1)
            self._logger.info(f"Az eszköz verziója {self.version}, a rejtett {self.hid}")

        self._properties.update(kwargs)

        if self.check_version and Props.TEMP_SENSOR.value in kwargs:
            self.check_version = False
            temp = self.get_property(Props.TEMP_SENSOR)
            self._logger.debug(f"Hőmérsékleti eltolás ellenőrzése, jelentett hőmérséklet: {temp}")
            if temp and temp < TEMP_OFFSET:
                self.version = "4.0"
                self._logger.info(
                    f"Az eszköz verziója {self.version}-ra változott, a {self.hid} el van rejtve."
                )
            self._logger.debug(f"Az eszköz hőmérsékletének {self.current_temperature} használata")

    async def push_state_update(self, wait_for: float = 30):
        """Push any pending state updates to the unit

        Args:
            wait_for (object): How long to wait for an update from the device, 0 for no wait
        """
        if not self._dirty:
            return

        if not self.device_cipher:
            await self.bind()

        self._logger.debug("Állapotfrissítések küldése ide: (%s)", str(self.device_info))

        props = {}
        for name in self._dirty:
            value = self._properties.get(name)
            self._logger.debug("Távoli állapotfrissítés küldése %s -> %s", name, value)
            props[name] = value
            if name == Props.TEMP_SET.value:
                props[Props.TEMP_BIT.value] = self._properties.get(Props.TEMP_BIT.value)
                props[Props.TEMP_UNIT.value] = self._properties.get(
                    Props.TEMP_UNIT.value
                )

        if not self._beep:
            self._logger.debug("Csipogó letiltása")
            props["Buzzer_ON_OFF"] = 1

        self._dirty.clear()

        try:
            await self.send(self.create_command_message(self.device_info, **props))

        except asyncio.TimeoutError:
            raise DeviceTimeoutError

    def __eq__(self, other):
        """Compare two devices for equality based on their properties state and device info."""
        return (
            self.device_info == other.device_info
            and self.raw_properties == other.raw_properties
            and self.device_cipher.key == other.device_cipher.key
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    @property
    def raw_properties(self) -> dict:
        return self._properties

    def get_property(self, name):
        """Generic lookup of properties tracked from the physical device"""
        if self._properties:
            return self._properties.get(name.value)
        return None

    def set_property(self, name, value):
        """Generic setting of properties for the physical device"""
        if not self._properties:
            self._properties = {}

        if self._properties.get(name.value) == value:
            return
        else:
            self._properties[name.value] = value
            if name.value not in self._dirty:
                self._dirty.append(name.value)

    @property
    def power(self) -> bool:
        return bool(self.get_property(Props.POWER))

    @power.setter
    def power(self, value: int):
        self.set_property(Props.POWER, int(value))

    @property
    def mode(self) -> int:
        return self.get_property(Props.MODE)

    @mode.setter
    def mode(self, value: int):
        self.set_property(Props.MODE, int(value))
        
    @property
    def quiet(self) -> int:
        return self.get_property(Props.QUIET)

    @quiet.setter
    def quiet(self, value: int):
        self.set_property(Props.QUIET, int(value))
        
""" eredeti kódrészlet       
    @property
    def quiet(self) -> bool:
        return self.get_property(Props.QUIET)

    @quiet.setter
    def quiet(self, value: bool):
        self.set_property(Props.QUIET, 2 if value else 0)
"""
    def _convert_to_units(self, value, bit):
        if self.temperature_units != TemperatureUnits.F.value:
            return value

        if value < TEMP_MIN_TABLE or value > TEMP_MAX_TABLE:
            raise ValueError(f"A megadott hőmérséklet ({value}) kívül esik a tartományon.")

        matching_temset = [t for t in TEMP_TABLE if t["temSet"] == value]

        try:
            f = next(t for t in matching_temset if t["temRec"] == bit)
        except StopIteration:
            f = matching_temset[0]

        return f["f"]

    @property
    def target_temperature(self) -> int:
        temset = self.get_property(Props.TEMP_SET)
        temrec = self.get_property(Props.TEMP_BIT)
        return self._convert_to_units(temset, temrec)

    @target_temperature.setter
    def target_temperature(self, value: int):
        def validate(val):
            if val > TEMP_MAX or val < TEMP_MIN:
                raise ValueError(f"A megadott hőmérséklet ({val}) kívül esik a tartományon.")

        if self.temperature_units == 1:
            rec = generate_temperature_record(value)
            validate(rec["temSet"])
            self.set_property(Props.TEMP_SET, rec["temSet"])
            self.set_property(Props.TEMP_BIT, rec["temRec"])
        else:
            validate(value)
            self.set_property(Props.TEMP_SET, int(value))

    @property
    def temperature_units(self) -> int:
        return self.get_property(Props.TEMP_UNIT)

    @temperature_units.setter
    def temperature_units(self, value: int):
        self.set_property(Props.TEMP_UNIT, int(value))

    @property
    def current_temperature(self) -> int:
        prop = self.get_property(Props.TEMP_SENSOR)
        bit = self.get_property(Props.TEMP_BIT)
        if prop is not None:
            v = self.version and int(self.version.split(".")[0])
            try:
                if v == 4:
                    return self._convert_to_units(prop, bit)
                elif prop != 0:
                    return self._convert_to_units(prop - TEMP_OFFSET, bit)
            except ValueError:
                logging.warning("Váratlan beállított hőmérsékleti érték (%s) konvertálása", prop)

        return self.target_temperature

    @property
    def fan_speed(self) -> int:
        return self.get_property(Props.FAN_SPEED)

    @fan_speed.setter
    def fan_speed(self, value: int):
        self.set_property(Props.FAN_SPEED, int(value))

    @property
    def fresh_air(self) -> bool:
        return bool(self.get_property(Props.FRESH_AIR))

    @fresh_air.setter
    def fresh_air(self, value: bool):
        self.set_property(Props.FRESH_AIR, int(value))

    @property
    def xfan(self) -> bool:
        return bool(self.get_property(Props.XFAN))

    @xfan.setter
    def xfan(self, value: bool):
        self.set_property(Props.XFAN, int(value))

    @property
    def anion(self) -> bool:
        return bool(self.get_property(Props.ANION))

    @anion.setter
    def anion(self, value: bool):
        self.set_property(Props.ANION, int(value))

    @property
    def sleep(self) -> bool:
        return bool(self.get_property(Props.SLEEP))

    @sleep.setter
    def sleep(self, value: bool):
        self.set_property(Props.SLEEP, int(value))
        self.set_property(Props.SLEEP_MODE, int(value))

    @property
    def light(self) -> bool:
        return bool(self.get_property(Props.LIGHT))

    @light.setter
    def light(self, value: bool):
        self.set_property(Props.LIGHT, int(value))

    @property
    def horizontal_swing(self) -> int:
        return self.get_property(Props.SWING_HORIZ)

    @horizontal_swing.setter
    def horizontal_swing(self, value: int):
        self.set_property(Props.SWING_HORIZ, int(value))

    @property
    def vertical_swing(self) -> int:
        return self.get_property(Props.SWING_VERT)

    @vertical_swing.setter
    def vertical_swing(self, value: int):
        self.set_property(Props.SWING_VERT, int(value))

    @property
    def turbo(self) -> bool:
        return bool(self.get_property(Props.TURBO))

    @turbo.setter
    def turbo(self, value: bool):
        self.set_property(Props.TURBO, int(value))

    @property
    def steady_heat(self) -> bool:
        return bool(self.get_property(Props.STEADY_HEAT))

    @steady_heat.setter
    def steady_heat(self, value: bool):
        self.set_property(Props.STEADY_HEAT, int(value))

    @property
    def power_save(self) -> bool:
        return bool(self.get_property(Props.POWER_SAVE))

    @power_save.setter
    def power_save(self, value: bool):
        self.set_property(Props.POWER_SAVE, int(value))

    @property
    def target_humidity(self) -> int:
        15 + (self.get_property(Props.HUM_SET) * 5)

    @target_humidity.setter
    def target_humidity(self, value: int):
        def validate(val):
            if value > HUMIDITY_MAX or val < HUMIDITY_MIN:
                raise ValueError(f"A megadott hőmérséklet ({val}) kívül esik a tartományon.")

        self.set_property(Props.HUM_SET, (value - 15) // 5)

    @property
    def dehumidifier_mode(self):
        return self.get_property(Props.DEHUMIDIFIER_MODE)

    @property
    def current_humidity(self) -> int:
        return self.get_property(Props.HUM_SENSOR)

    @property
    def clean_filter(self) -> bool:
        return bool(self.get_property(Props.CLEAN_FILTER))

    @property
    def water_full(self) -> bool:
        return bool(self.get_property(Props.WATER_FULL))

    @property
    def beep(self) -> bool:
        return self._beep

    @beep.setter
    def beep(self, value: bool):
        self._beep = bool(value)
