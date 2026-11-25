"""Dragino models, commands, and official ChirpStack/TTS catalog identities."""

from datetime import datetime
from math import floor
from typing import ClassVar

from .decoders import (
    CHANNELS,
    LDS02_MODE,
    LDS02_STATUS_MASK,
    LWL02_MODE,
    LWL02_STATUS_MASK,
)
from .device import DecoderProtocol, DraginoDevice

VENDOR_ID = 676


class LHT65(DraginoDevice):
    """Temperature and humidity sensor with an optional external probe."""

    identifiers = {"tts": ("dragino", "lht65")}
    model_name = "LHT65"
    _protocol: ClassVar[DecoderProtocol] = "lht65"
    _ports = (2,)

    @property
    def temperature(self) -> float | None:
        """Internal temperature in degrees Celsius."""
        return self._float("temperature")

    @property
    def humidity(self) -> float | None:
        """Relative humidity in percent."""
        return self._float("humidity")

    @property
    def external_temperature(self) -> float | None:
        """External probe temperature in degrees Celsius."""
        return self._float("external_temperature")

    @property
    def battery_voltage(self) -> float | None:
        """Battery voltage in volts."""
        return self._float("battery_voltage")

    @property
    def external_voltage(self) -> float | None:
        """External ADC voltage in volts."""
        return self._float("external_voltage")

    @property
    def illuminance(self) -> float | None:
        """External light sensor illuminance in lux."""
        return self._float("illuminance")

    @property
    def external_count(self) -> int | None:
        """External interrupt count."""
        return self._int("external_count")

    @property
    def external_input(self) -> bool | None:
        """External interrupt pin level."""
        return self._bool("external_input")

    @property
    def external_interrupt(self) -> bool | None:
        """Whether the external interrupt triggered this uplink."""
        return self._bool("external_interrupt")

    @property
    def external_sensor_disconnected(self) -> bool | None:
        """Whether the external probe is disconnected."""
        return self._bool("external_sensor_disconnected")

    @property
    def reported_battery_status(self) -> int | None:
        """Vendor battery status, from 0 (ultra low) to 3 (good)."""
        return self._int("reported_battery_status")


class ContactDevice(DraginoDevice):
    """Door or leak status, counters, and battery voltage."""

    _ports = (10,)
    mode: ClassVar[int]
    """Work mode of the model's own status report."""
    status_mask: ClassVar[int]
    """Status-byte bit that reports `active`."""

    @property
    def active(self) -> bool | None:
        """Whether the door is open or a leak is detected."""
        return self._bool("active")

    @property
    def alarm(self) -> bool | None:
        """Whether the open-duration alarm is active."""
        return self._bool("alarm")

    @property
    def battery_voltage(self) -> float | None:
        """Battery voltage in volts."""
        return self._float("battery_voltage")

    @property
    def event_count(self) -> int | None:
        """Number of door openings or leak events."""
        return self._int("event_count")

    @property
    def last_duration(self) -> int | None:
        """Duration of the last event in minutes."""
        return self._int("last_duration")

    @property
    def battery_percentage(self) -> int | None:
        """Estimate charge using the device profile's voltage range."""
        if (voltage := self.battery_voltage) is None:
            return None
        voltage = min(max(voltage, 2.1), 3.1)
        return floor((voltage - 2.1) / (3.1 - 2.1) * 100 + 0.5)


class LDS02(ContactDevice):
    """Door sensor."""

    identifiers = {
        "tts": ("dragino", "lds02"),
        "chirpstack": (VENDOR_ID, "55deef19-c13c-4b69-a10d-2e89f6398a02"),
    }
    model_name = "LDS02"
    mode = LDS02_MODE
    status_mask = LDS02_STATUS_MASK
    _protocol: ClassVar[DecoderProtocol] = "lds02"


class LWL02(ContactDevice):
    """Water leak sensor."""

    identifiers = {
        "tts": ("dragino", "lwl02"),
        "chirpstack": (VENDOR_ID, "b9a99932-c5e0-40fb-a673-85c24640cf7c"),
    }
    model_name = "LWL02"
    mode = LWL02_MODE
    status_mask = LWL02_STATUS_MASK
    _protocol: ClassVar[DecoderProtocol] = "lwl02"

    async def async_set_reporting_interval(self, seconds: int) -> None:
        """Queue a keep-alive interval in seconds."""
        if not 1 <= seconds <= 0xFFFFFF:
            raise ValueError(
                "Reporting interval must be between 1 and 16777215 seconds"
            )
        await self.async_send_downlink(
            data=b"\x01" + seconds.to_bytes(3, "big"),
            f_port=1,
            wait_for_ack=False,
        )

    async def async_reset_count(self) -> None:
        """Queue a reset of the event count and last leak duration."""
        await self.async_send_downlink(data=b"\xa6\x01", f_port=1, wait_for_ack=False)


class CPL03LB(DraginoDevice):
    """A single-contact, three-counter, or three-interrupt sensor."""

    identifiers = {
        "chirpstack": (VENDOR_ID, "621f921e-4685-4421-b8a0-b4cc6b5d77b8"),
        "tts": ("dragino", "cpl03-lb"),
    }
    model_name = "CPL03-LB"
    _protocol: ClassVar[DecoderProtocol] = "cpl03lb"
    _ports = (2, 5, 6, 7)

    @property
    def work_mode(self) -> str | None:
        """Reported input mode: cpl01, cpl03, or interrupt."""
        return self._str("work_mode")

    @property
    def counts_are_cumulative(self) -> bool | None:
        """Whether counters accumulate rather than reset after each uplink."""
        return self._bool("counts_are_cumulative")

    @property
    def contact_open(self) -> bool | None:
        """Single-contact mode: whether the contact is open."""
        return self._bool("contact_open")

    @property
    def alarm(self) -> bool | None:
        """Single-contact mode: whether the open-duration alarm is active."""
        return self._bool("alarm")

    @property
    def pulse_count(self) -> int | None:
        """Single-contact mode: pulse count."""
        return self._int("pulse_count")

    @property
    def last_duration(self) -> int | None:
        """Single-contact mode: duration of the last open event in seconds."""
        return self._int("last_duration")

    @property
    def pa8_count(self) -> int | None:
        """Three-counter mode: PA8 pulse count."""
        return self._int("pa8_count")

    @property
    def pa4_count(self) -> int | None:
        """Three-counter mode: PA4 pulse count."""
        return self._int("pa4_count")

    @property
    def pb15_count(self) -> int | None:
        """Three-counter mode: PB15 pulse count."""
        return self._int("pb15_count")

    @property
    def pa8_open(self) -> bool | None:
        """Interrupt mode: whether the PA8 contact is open."""
        return self._bool("pa8_open")

    @property
    def pa4_open(self) -> bool | None:
        """Interrupt mode: whether the PA4 contact is open."""
        return self._bool("pa4_open")

    @property
    def pb15_open(self) -> bool | None:
        """Interrupt mode: whether the PB15 contact is open."""
        return self._bool("pb15_open")

    @property
    def battery_voltage(self) -> float | None:
        """Battery voltage in volts from the device-status report."""
        return self._float("battery_voltage")

    @property
    def firmware_version(self) -> str | None:
        """Firmware version from the device-status report."""
        return self._str("firmware_version", metadata=True)

    async def async_request_device_status(self) -> None:
        """Queue a device-information request for the next receive window."""
        await self.async_send_downlink(data=b"\x26\x01", f_port=2, wait_for_ack=False)


class LT22222(DraginoDevice):
    """Two-relay, two-output I/O controller with analog and digital inputs."""

    identifiers = {
        "chirpstack": (VENDOR_ID, "cb0a7bef-eaa0-4c61-a0b6-ce33e6ecbc4f"),
        "tts": ("dragino", "lt22222-l"),
    }
    model_name = "LT-22222-L"
    _protocol: ClassVar[DecoderProtocol] = "lt22222"
    _ports = (2, 5)

    @property
    def mode(self) -> int | None:
        """Reported work mode, from 1 to 5."""
        return self._int("mode")

    @property
    def relays(self) -> dict[int, bool | None]:
        """Relay states by channel."""
        return {channel: self._bool(f"relay_{channel}") for channel in CHANNELS}

    @property
    def digital_outputs(self) -> dict[int, bool | None]:
        """Active-low digital output states by channel."""
        return {
            channel: self._bool(f"digital_output_{channel}") for channel in CHANNELS
        }

    @property
    def digital_inputs(self) -> dict[int, bool | None]:
        """Digital input levels by channel, reported in mode 1."""
        return {channel: self._bool(f"digital_input_{channel}") for channel in CHANNELS}

    @property
    def voltages(self) -> dict[int, float | None]:
        """Analog input voltages in volts by channel."""
        return {channel: self._float(f"voltage_{channel}") for channel in CHANNELS}

    @property
    def currents(self) -> dict[int, float | None]:
        """Analog input currents in milliamperes by channel."""
        return {channel: self._float(f"current_{channel}") for channel in CHANNELS}

    @property
    def digital_counts(self) -> dict[int, int | None]:
        """Digital input pulse counts by channel."""
        return {channel: self._int(f"digital_count_{channel}") for channel in CHANNELS}

    @property
    def voltage_count(self) -> int | None:
        """Analog-voltage-triggered count, reported in mode 4."""
        return self._int("voltage_count")

    @property
    def firmware_version(self) -> str | None:
        """Firmware version from the device-status report."""
        return self._str("firmware_version", metadata=True)

    async def async_set_relay(
        self, channel: int, on: bool, *, expires_at: datetime | None = None
    ) -> None:
        """Set a relay and wait for acknowledgement."""
        if channel not in CHANNELS:
            raise ValueError("Relay channel must be 1 or 2")
        states = [0x11, 0x11]
        states[channel - 1] = int(on)
        await self.async_send_downlink(
            data=bytes((0x03, *states)),
            f_port=2,
            expires_at=expires_at,
        )

    async def async_set_digital_output(
        self, channel: int, on: bool, *, expires_at: datetime | None = None
    ) -> None:
        """Enable an active-low output and await its command acknowledgement."""
        if channel not in CHANNELS:
            raise ValueError("Digital output channel must be 1 or 2")
        # The protocol includes DO3 even though this model has no third output.
        states = [0x11, 0x11, 0x11]
        states[channel - 1] = int(on)
        await self.async_send_downlink(
            data=bytes((0x02, *states)),
            f_port=2,
            expires_at=expires_at,
        )
