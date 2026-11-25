"""Device collection lifecycle and merging of partial or out-of-order uplinks."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from lorawan_connection import DeviceDescriptor, GatewayReception, UplinkEvent
from lorawan_connection.mock import MockConnection

from dragino_lorawan import CPL03LB, LHT65, LT22222, DraginoDevices

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _seconds(seconds: int) -> datetime:
    return T0 + timedelta(seconds=seconds)


async def test_collection_lifecycle(descriptor: DeviceDescriptor) -> None:
    """Discover a device, decode the TTN example, and ignore invalid frames."""
    connection = MockConnection([descriptor], stack_type="tts")
    collection = DraginoDevices(connection)
    await collection.async_setup()
    device = collection.devices[descriptor.dev_eui]
    assert isinstance(device, LHT65)
    event = UplinkEvent(
        received_at=datetime.now(UTC),
        descriptor=descriptor,
        f_port=2,
        data=bytes.fromhex("cbf60b0d0376010add7fff"),
    )
    connection.emit(event)
    assert device.temperature == 28.29
    assert device.humidity == 88.6
    assert device.external_temperature == 27.81
    assert device.battery_voltage == 3.062
    assert device.value("reported_battery_status") == 3
    connection.emit(replace(event, data=b"\x01"))
    connection.emit(replace(event, f_port=99))
    connection.emit(
        replace(
            event, received_at=event.received_at - timedelta(seconds=1), data=bytes(11)
        )
    )
    assert device.temperature == 28.29
    collection.close()


def test_signal_quality(descriptor: DeviceDescriptor) -> None:
    """Track the strongest reception of the latest uplink on any port."""
    device = LHT65(descriptor)
    event = UplinkEvent(
        descriptor=descriptor,
        received_at=_seconds(1),
        f_port=99,
        data=b"",
        receptions=(
            GatewayReception(gateway_id="a", rssi=-110, snr=-3.5),
            GatewayReception(gateway_id="b", rssi=-80, snr=7.25),
        ),
    )
    device.handle_event(event)
    assert (device.rssi, device.snr) == (-80, 7.25)
    device.handle_event(
        replace(
            event,
            received_at=T0,
            receptions=(GatewayReception(gateway_id="a", rssi=-50, snr=9),),
        )
    )
    assert device.rssi == -80


def test_cpl03lb_partial_and_stale_updates(descriptor: DeviceDescriptor) -> None:
    """Retain independent reports and reject older values without notifying."""
    device = CPL03LB(descriptor)
    notified = Mock()
    device.add_update_listener(notified)
    event = UplinkEvent(
        descriptor=descriptor,
        received_at=T0,
        f_port=2,
        data=bytes.fromhex("0300000200003c00000000"),
    )
    device.handle_event(event)
    status = replace(
        event, received_at=_seconds(2), f_port=5, data=bytes.fromhex("20011101ff0b45")
    )
    device.handle_event(status)
    # A status report must not suppress a delayed but newer contact reading.
    contact = replace(event, received_at=_seconds(1), data=bytes(11))
    device.handle_event(contact)
    assert device.contact_open is False
    assert device.pulse_count == 0
    assert device.battery_voltage == 2.885
    assert device.firmware_version == "1.1.1"
    assert notified.call_count == 3
    for ignored in (
        event,
        replace(status, received_at=T0),
        replace(status, data=b""),
        replace(status, f_port=99),
    ):
        device.handle_event(ignored)
    assert notified.call_count == 3
    device.close()
    device.handle_event(replace(event, received_at=status.received_at))
    assert notified.call_count == 3
    assert device.contact_open is False


def test_cpl03lb_mode_changes(descriptor: DeviceDescriptor) -> None:
    """Clear all inactive-mode readings, including stale interrupt levels."""
    device = CPL03LB(descriptor)
    event = UplinkEvent(descriptor=descriptor, received_at=T0, f_port=7, data=b"\x00")
    device.handle_event(event)
    assert device.work_mode == "interrupt"
    assert device.pa8_open is True
    single = replace(
        event,
        received_at=_seconds(1),
        f_port=2,
        data=bytes.fromhex("0300000200003c00000000"),
    )
    device.handle_event(single)
    assert device.work_mode == "cpl01"
    assert device.contact_open is True
    assert device.pa8_open is None
    assert device.pa8_count is None
    pulse = replace(
        event,
        received_at=_seconds(2),
        f_port=6,
        data=bytes.fromhex("08000005000006000007"),
    )
    device.handle_event(pulse)
    assert device.work_mode == "cpl03"
    assert device.pa8_count == 5
    assert device.contact_open is None
    assert device.alarm is None
    assert device.pulse_count is None
    assert device.last_duration is None
    device.handle_event(single)
    device.handle_event(event)
    assert device.work_mode == "cpl03"
    assert device.pa8_count == 5
    assert device.pa8_open is None
    device.handle_event(replace(event, received_at=_seconds(3)))
    assert device.work_mode == "interrupt"
    assert device.pa8_count is None
    assert device.pa8_open is True
    assert device.counts_are_cumulative is None


def test_lt22222_status(descriptor: DeviceDescriptor) -> None:
    """Keep the firmware version separate from I/O readings."""
    device = LT22222(descriptor)
    notified = Mock()
    device.add_update_listener(notified)
    # EU868, no sub-band, firmware 1.1.3, 600 s interval.
    status = UplinkEvent(
        descriptor=descriptor,
        received_at=T0,
        f_port=5,
        data=bytes.fromhex("01ff0113000258"),
    )
    device.handle_event(status)
    assert device.firmware_version == "1.1.3"
    assert device.mode is None
    assert device.relays == {1: None, 2: None}
    assert notified.call_count == 1
    newer = bytes.fromhex("01ff0220000258")
    for ignored in (
        replace(status, received_at=T0 - timedelta(seconds=1), data=newer),
        replace(status, data=newer[:6]),
        replace(status, f_port=4, data=newer),
    ):
        device.handle_event(ignored)
    assert device.firmware_version == "1.1.3"
    assert notified.call_count == 1


def test_lt22222_io_reports(descriptor: DeviceDescriptor) -> None:
    """Expose channel readings as dictionaries and ignore trigger reports."""
    device = LT22222(descriptor)
    event = UplinkEvent(
        descriptor=descriptor,
        received_at=T0,
        f_port=2,
        # Mode 1: 1.5 V, -0.25 V, 4 mA, 20 mA, RO1 on, DO2 low, DI1 high.
        data=bytes.fromhex("05dcff060fa04e208a0041"),
    )
    device.handle_event(event)
    assert device.mode == 1
    assert device.voltages == {1: 1.5, 2: -0.25}
    assert device.currents == {1: 4.0, 2: 20.0}
    assert device.relays == {1: True, 2: False}
    assert device.digital_outputs == {1: False, 2: True}
    assert device.digital_inputs == {1: True, 2: False}
    assert device.digital_counts == {1: None, 2: None}
    device.handle_event(
        replace(event, received_at=_seconds(1), data=bytes(10) + b"\x46")
    )
    assert device.mode == 1
    device.handle_event(
        replace(event, received_at=T0 - timedelta(seconds=1), data=bytes(10) + b"\x44")
    )
    assert device.mode == 1
    assert device.voltage_count is None
