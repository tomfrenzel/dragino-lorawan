"""Dragino device models for ChirpStack and The Things Stack."""

from lorawan_connection import DeviceCollection

from .device import DraginoDevice
from .models import CPL03LB, LDS02, LHT65, LT22222, LWL02, VENDOR_ID, ContactDevice
from .payload import DecodedPayload, Value


class DraginoDevices(DeviceCollection[DraginoDevice]):
    """Discover Dragino devices using official catalog identities."""

    DEVICES = (LT22222, LHT65, LDS02, LWL02, CPL03LB)


__all__ = [
    "CPL03LB",
    "LDS02",
    "LHT65",
    "LT22222",
    "LWL02",
    "VENDOR_ID",
    "ContactDevice",
    "DecodedPayload",
    "DraginoDevice",
    "DraginoDevices",
    "Value",
]
