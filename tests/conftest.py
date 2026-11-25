"""Shared fixtures for Dragino device tests."""

from lorawan_connection import DeviceDescriptor
import pytest

from dragino_lorawan import LHT65


@pytest.fixture
def descriptor() -> DeviceDescriptor:
    """Describe a device using its catalog identity."""
    brand_id, model_id = LHT65.identifiers["tts"]
    return DeviceDescriptor(
        network_id="network",
        dev_eui="0201010101010101",
        name="Garden",
        application_id="application",
        profile_id="local-profile",
        stack="tts",
        brand_id=brand_id,
        model_id=model_id,
    )
