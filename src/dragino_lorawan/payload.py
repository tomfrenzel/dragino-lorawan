"""Decoded values shared by the Dragino wire protocols."""

from dataclasses import dataclass, field

type Value = None | bool | int | float | str


@dataclass
class DecodedPayload:
    """Readings and device metadata from one complete uplink.

    An empty payload is a valid frame that carries no live readings, such as a
    history, configuration, or identification report.
    """

    values: dict[str, Value] = field(default_factory=dict)
    metadata: dict[str, Value] = field(default_factory=dict)


def unsigned(data: bytes) -> int:
    """Read an unsigned big-endian integer."""
    return int.from_bytes(data, "big")


def signed(data: bytes, divisor: float = 1) -> float:
    """Read a signed big-endian value and scale it."""
    return int.from_bytes(data, "big", signed=True) / divisor


def version(major: int, minor_patch: int) -> str:
    """Read a firmware version from its major and packed minor/patch bytes."""
    return f"{major & 0x0F}.{minor_patch >> 4}.{minor_patch & 0x0F}"
