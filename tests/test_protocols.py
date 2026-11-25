"""Decoder boundaries and behavior the reference codecs do not cover."""

import pytest

from dragino_lorawan import CPL03LB, LDS02, LHT65, LT22222, LWL02, DecodedPayload


@pytest.mark.parametrize(
    ("payload", "key", "expected"),
    [
        ("cbeaff9c026d01ff387fff", "external_temperature", -2),
        ("cbf60b0d0376817fff7fff", "external_temperature", None),
        ("cbf60b0d03760500647fff", "illuminance", 100),
        ("cbf60b0d0376060bb87fff", "external_voltage", 3),
        ("cbf60b0d0376080000000a", "external_count", 10),
    ],
)
def test_lht65_extensions(payload: str, key: str, expected: float | None) -> None:
    """Decode external probes and disconnected sensors."""
    assert LHT65.decode(2, bytes.fromhex(payload)).values[key] == expected


@pytest.mark.parametrize(
    "payload",
    [
        "cbea0105026d4101aa7fff",  # Datalog reply.
        "cbf60b0d03760f01020304",  # External probe identifier.
    ],
)
def test_lht65_non_measurements(payload: str) -> None:
    """Ignore frames that do not carry a current reading."""
    assert LHT65.decode(2, bytes.fromhex(payload)) == DecodedPayload()


@pytest.mark.parametrize("payload", ["01", "cbf60b0d037601", "cbf60b0d0fff010add7fff"])
def test_lht65_invalid_payload(payload: str) -> None:
    """Reject incomplete frames and invalid humidity."""
    with pytest.raises(ValueError):
        LHT65.decode(2, bytes.fromhex(payload))


@pytest.mark.parametrize(
    ("model", "payload", "expected"),
    [
        (
            LDS02,
            "8bd00100000500000700",
            {"active": True, "event_count": 5, "last_duration": 7, "alarm": False},
        ),
        (
            LWL02,
            "4bd002000003000004",
            {"active": True, "event_count": 3, "last_duration": 4, "alarm": None},
        ),
        (
            LWL02,
            "8bd00300000000000001",
            {"active": False, "event_count": None, "last_duration": None},
        ),
    ],
)
def test_contact_modes(
    model: type[LDS02 | LWL02], payload: str, expected: dict[str, object]
) -> None:
    """Decode each model's own status bit; combined mode has no counters."""
    values = model.decode(10, bytes.fromhex(payload)).values
    assert values.items() >= expected.items()
    assert values["battery_voltage"] == 3.024


@pytest.mark.parametrize(
    ("model", "payload"),
    [
        (LDS02, "0bd0020000000000000000"),  # Leak mode on a door sensor.
        (LWL02, "0bd0010000000000000000"),  # Door mode on a leak sensor.
        (LDS02, "0bd001000000000000"),  # Door mode requires the alarm byte.
        (LWL02, "0bd0"),
    ],
)
def test_contact_invalid_payload(model: type[LDS02 | LWL02], payload: str) -> None:
    """Reject other models' modes and truncated frames."""
    with pytest.raises(ValueError):
        model.decode(10, bytes.fromhex(payload))


@pytest.mark.parametrize(
    ("port", "payload", "expected"),
    [
        (
            2,
            "37ffffff010203ffffffff",
            {
                "work_mode": "cpl01",
                "counts_are_cumulative": False,
                "contact_open": True,
                "alarm": True,
                "pulse_count": 16777215,
                "last_duration": 66051,
            },
        ),
        (
            2,
            "0000000200003c00000000",
            {"contact_open": False, "alarm": False, "last_duration": 60},
        ),
        (
            6,
            "3f800000ffffff01020305",
            {
                "work_mode": "cpl03",
                "counts_are_cumulative": False,
                "pa8_count": 8388608,
                "pa4_count": 16777215,
                "pb15_count": 66051,
            },
        ),
        (
            6,
            "08000005000006ffffff",
            {
                "counts_are_cumulative": True,
                "pa8_count": 5,
                "pa4_count": 6,
                "pb15_count": 16777215,
            },
        ),
        (7, "19", {"pa8_open": False, "pa4_open": True, "pb15_open": False}),
        (
            7,
            "26ffffffffffffffffffff",
            {"pa8_open": True, "pa4_open": False, "pb15_open": True},
        ),
        (5, "20011101ff0b45", {"firmware_version": "1.1.1", "battery_voltage": 2.885}),
        (5, "20011102030e10", {"firmware_version": "1.1.1", "battery_voltage": 3.6}),
    ],
)
def test_cpl03lb_codec_examples(
    port: int, payload: str, expected: dict[str, object]
) -> None:
    """Match the ChirpStack catalog's unsigned values, units, and contact bits."""
    result = CPL03LB.decode(port, bytes.fromhex(payload))
    assert {**result.values, **result.metadata}.items() >= expected.items()


@pytest.mark.parametrize(
    ("port", "payload"),
    [
        (port, data[:length])
        for port, data in (
            (2, bytes(11)),
            (5, bytes.fromhex("20011101ff0b45")),
            (6, bytes.fromhex("08000005000006000007")),
            (7, b"\x00"),
        )
        for length in range(len(data))
    ]
    + [
        (2, bytes(12)),
        (5, bytes.fromhex("20011101ff0b4500")),
        (6, b"\x08" + bytes(11)),
        (2, b"\x08" + bytes(10)),
        (6, bytes(10)),
        (5, bytes.fromhex("21011101ff0b45")),
        (5, bytes.fromhex("20011100ff0b45")),
        (5, bytes.fromhex("2001110fff0b45")),
    ],
)
def test_cpl03lb_invalid_payload(port: int, payload: bytes) -> None:
    """Reject truncated, oversized, mismatched-mode, and wrong-model packets."""
    with pytest.raises(ValueError):
        CPL03LB.decode(port, payload)


@pytest.mark.parametrize("port", [3, 4, 8, 99])
def test_cpl03lb_non_measurements(port: int) -> None:
    """Do not turn history, configuration, or unknown layouts into live readings."""
    assert CPL03LB.decode(port, bytes(11)) == DecodedPayload()


# The first payload is the example in Dragino's LT-22222-L manual:
# https://docs.dragino.com/docs/LoRaWAN-End-Node/io-controllers-sensor-nodes/lt-22222-l/#34226-query-firmware-version-frequency-band-subband-and-tdc-time
@pytest.mark.parametrize(
    ("payload", "firmware"),
    [
        ("01ff0160000258", "1.6.0"),
        ("0208f2ab0004b0", "2.10.11"),
        ("0fff0161000258", "1.6.1"),
    ],
)
def test_lt22222_firmware(payload: str, firmware: str) -> None:
    """Decode the vendor example and boundary status reports."""
    result = LT22222.decode(5, bytes.fromhex(payload))
    assert result == DecodedPayload(metadata={"firmware_version": firmware})


@pytest.mark.parametrize(
    "payload", ["01ff02200002", "01ff0220000258ff", "00ff0220000258", "10ff0220000258"]
)
def test_lt22222_invalid_status(payload: str) -> None:
    """Reject truncated, oversized, and unknown-band status reports."""
    with pytest.raises(ValueError):
        LT22222.decode(5, bytes.fromhex(payload))


@pytest.mark.parametrize("mode", [0, 6, 0x3F])
def test_lt22222_trigger_reports(mode: int) -> None:
    """Trigger reports contain flags, not input measurements or output states."""
    assert LT22222.decode(2, bytes(10) + bytes([0x40 | mode])) == DecodedPayload()


def test_lt22222_inactive_mode_fields() -> None:
    """Fields unused by the reported mode are explicitly cleared."""
    values = LT22222.decode(2, bytes.fromhex("0000000a0000000bc00042")).values
    assert values["mode"] == 2
    assert values["relay_1"] is values["relay_2"] is True
    assert values["digital_count_1"] == 10
    assert values["digital_count_2"] == 11
    for name in ("voltage_1", "current_1", "digital_input_1", "voltage_count"):
        assert name in values
        assert values[name] is None
