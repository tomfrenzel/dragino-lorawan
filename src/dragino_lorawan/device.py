"""Merge Dragino uplinks while preserving partial and out-of-order readings."""

from collections.abc import Callable
from datetime import datetime
import logging
from typing import ClassVar, Literal, override

from lorawan_connection import (
    Device,
    DeviceDescriptor,
    DeviceEvent,
    EventType,
    UplinkEvent,
)

from .decoders import (
    decode_cpl03lb,
    decode_lds02,
    decode_lht65,
    decode_lt22222,
    decode_lwl02,
)
from .payload import DecodedPayload, Value

_LOGGER = logging.getLogger(__name__)

type DecoderProtocol = Literal["lht65", "lds02", "lwl02", "lt22222", "cpl03lb"]

_DECODERS: dict[DecoderProtocol, Callable[[int, bytes], DecodedPayload]] = {
    "lht65": decode_lht65,
    "lds02": decode_lds02,
    "lwl02": decode_lwl02,
    "lt22222": decode_lt22222,
    "cpl03lb": decode_cpl03lb,
}


class DraginoDevice(Device):
    """Latest decoded values and metadata, plus the link quality of each uplink."""

    model_name: ClassVar[str]
    _protocol: ClassVar[DecoderProtocol]
    _ports: ClassVar[tuple[int, ...]]

    def __init__(self, descriptor: DeviceDescriptor) -> None:
        super().__init__(descriptor)
        self.values: dict[str, Value] = {}
        self.metadata: dict[str, Value] = {}
        self.rssi: float | None = None
        self.snr: float | None = None
        self._value_times: dict[str, datetime] = {}
        self._metadata_times: dict[str, datetime] = {}
        self._signal_updated: datetime | None = None

    @classmethod
    def decode(cls, f_port: int, data: bytes) -> DecodedPayload:
        """Decode one complete payload; malformed frames raise ValueError."""
        return _DECODERS[cls._protocol](f_port, data)

    def value(self, name: str) -> Value:
        """Read a decoded value, or None before it arrives or when not reported."""
        return self.values.get(name)

    def _bool(self, name: str) -> bool | None:
        value = self.values.get(name)
        return value if isinstance(value, bool) else None

    def _int(self, name: str) -> int | None:
        value = self.values.get(name)
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    def _float(self, name: str) -> float | None:
        value = self.values.get(name)
        return (
            float(value)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
            else None
        )

    def _str(self, name: str, *, metadata: bool = False) -> str | None:
        value = (self.metadata if metadata else self.values).get(name)
        return value if isinstance(value, str) else None

    @override
    def handle_event(self, event: DeviceEvent) -> None:
        if self.closed or event.type != EventType.UPLINK:
            return
        self._update_signal(event)
        if event.f_port not in self._ports:
            return
        try:
            payload = self.decode(event.f_port, event.data)
        except ValueError as err:
            _LOGGER.debug(
                "Ignoring %s uplink on port %s: %s", self.model_name, event.f_port, err
            )
            return
        changed = self._merge(
            self.values, self._value_times, payload.values, event.received_at
        )
        if self._merge(
            self.metadata, self._metadata_times, payload.metadata, event.received_at
        ):
            changed = True
        if changed:
            self.notify()

    @staticmethod
    def _merge(
        target: dict[str, Value],
        times: dict[str, datetime],
        values: dict[str, Value],
        received_at: datetime,
    ) -> bool:
        """Apply each value unless a newer uplink already reported it."""
        changed = False
        for name, value in values.items():
            if name in times and received_at < times[name]:
                continue
            target[name] = value
            times[name] = received_at
            changed = True
        return changed

    def _update_signal(self, event: UplinkEvent) -> None:
        """Keep the strongest gateway reception of the latest uplink."""
        if (
            self._signal_updated is not None
            and event.received_at < self._signal_updated
        ):
            return
        measured = [
            reception for reception in event.receptions if reception.rssi is not None
        ]
        if not measured:
            return
        best = max(measured, key=lambda reception: reception.rssi or 0)
        self.rssi = best.rssi
        self.snr = best.snr
        self._signal_updated = event.received_at
        # Notifications are coalesced while the device handles an event.
        self.notify()
