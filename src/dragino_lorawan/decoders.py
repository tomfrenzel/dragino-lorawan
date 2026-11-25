"""Dragino payload decoders, following the TTN and ChirpStack codecs."""

from .payload import DecodedPayload, Value, signed, unsigned, version

LDS02_MODE, LDS02_STATUS_MASK = 1, 0x80
LWL02_MODE, LWL02_STATUS_MASK = 2, 0x40
CHANNELS = (1, 2)

_SINGLE_FIELDS = ("contact_open", "alarm", "pulse_count", "last_duration")
_COUNTER_FIELDS = ("pa8_count", "pa4_count", "pb15_count")
_CONTACT_FIELDS = ("pa8_open", "pa4_open", "pb15_open")
_LENGTHS = {2: (11,), 5: (7,), 6: (10, 11)}


def decode_cpl03lb(f_port: int, data: bytes) -> DecodedPayload:
    """Decode live reports; history and configuration are not measurements.

    Each input-mode frame sets every input field, clearing the readings of the
    inactive modes.
    """
    if f_port not in (2, 5, 6, 7):
        return DecodedPayload()
    if (f_port == 7 and not data) or (
        f_port != 7 and len(data) not in _LENGTHS[f_port]
    ):
        raise ValueError("Invalid payload length")
    if f_port == 5:
        if data[0] != 0x20:
            raise ValueError("Unexpected sensor model")
        if not 1 <= data[3] <= 14:
            raise ValueError("Unknown frequency band")
        return DecodedPayload(
            {"battery_voltage": unsigned(data[5:7]) / 1000},
            {"firmware_version": version(data[1], data[2])},
        )
    if f_port == 7:
        # Status bits mean CLOSED; interrupt bits do not indicate the level.
        return DecodedPayload(
            {
                **dict.fromkeys((*_SINGLE_FIELDS, *_COUNTER_FIELDS)),
                "work_mode": "interrupt",
                "counts_are_cumulative": None,
                "pa8_open": not data[0] & 0x01,
                "pa4_open": not data[0] & 0x04,
                "pb15_open": not data[0] & 0x10,
            }
        )
    if bool(data[0] & 0x08) != (f_port == 6):
        raise ValueError("Unexpected work mode")
    values: dict[str, Value] = {
        "work_mode": "cpl01" if f_port == 2 else "cpl03",
        "counts_are_cumulative": not data[0] & 0x20,
    }
    if f_port == 2:
        values.update(dict.fromkeys((*_COUNTER_FIELDS, *_CONTACT_FIELDS)))
        values.update(
            contact_open=bool(data[0] & 0x01),
            alarm=bool(data[0] & 0x02),
            pulse_count=unsigned(data[1:4]),
            last_duration=unsigned(data[4:7]),
        )
    else:
        values.update(dict.fromkeys((*_SINGLE_FIELDS, *_CONTACT_FIELDS)))
        values.update(
            pa8_count=unsigned(data[1:4]),
            pa4_count=unsigned(data[4:7]),
            pb15_count=unsigned(data[7:10]),
        )
    return DecodedPayload(values)


def decode_lds02(f_port: int, data: bytes) -> DecodedPayload:
    """Decode an LDS02 door report."""
    if f_port != 10:
        return DecodedPayload()
    if len(data) < 3:
        raise ValueError("Truncated contact sensor data")
    if data[2] not in (LDS02_MODE, 3):
        raise ValueError("Unexpected work mode")
    if len(data) != 10:
        raise ValueError("Invalid contact sensor frame length")
    counters = data[2] == LDS02_MODE
    return DecodedPayload(
        {
            "active": bool(data[0] & LDS02_STATUS_MASK),
            "battery_voltage": (unsigned(data[:2]) & 0x3FFF) / 1000,
            "alarm": bool(data[9] & 1),
            "event_count": unsigned(data[3:6]) if counters else None,
            "last_duration": unsigned(data[6:9]) if counters else None,
        }
    )


def decode_lht65(f_port: int, data: bytes) -> DecodedPayload:
    """Decode a port-2 reading; datalog and probe ID frames have no readings."""
    if f_port != 2:
        return DecodedPayload()
    if len(data) < 7:
        raise ValueError("Truncated LHT65 data")
    if data[6] & 0x40:
        return DecodedPayload()  # Datalog response, not a current reading.
    if len(data) != 11:
        raise ValueError("Invalid LHT65 frame length")
    extension = data[6] & 0x0F
    if extension == 15:
        return DecodedPayload()  # External probe identifier frame.
    humidity = (unsigned(data[4:6]) & 0xFFF) / 10
    if not 0 <= humidity <= 100:
        raise ValueError("Humidity outside sensor range")
    disconnected = bool(data[6] & 0x80)
    values: dict[str, Value] = {
        "temperature": signed(data[2:4], 100),
        "humidity": humidity,
        "external_sensor_disconnected": disconnected,
    }
    if extension == 9:
        values["external_temperature"] = signed(data[:2], 100)
        values["reported_battery_status"] = data[4] >> 6
    else:
        values["battery_voltage"] = (unsigned(data[:2]) & 0x3FFF) / 1000
        values["reported_battery_status"] = data[0] >> 6
    if extension == 1:
        raw = unsigned(data[7:9])
        values["external_temperature"] = (
            None if disconnected or raw == 0x7FFF else signed(data[7:9], 100)
        )
    elif extension == 4:
        values["external_input"] = bool(data[7])
        values["external_interrupt"] = bool(data[8])
    elif extension == 5:
        values["illuminance"] = unsigned(data[7:9])
    elif extension == 6:
        values["external_voltage"] = unsigned(data[7:9]) / 1000
    elif extension in (7, 8):
        values["external_count"] = unsigned(data[7 : 9 if extension == 7 else 11])
    return DecodedPayload(values)


def decode_lt22222(f_port: int, data: bytes) -> DecodedPayload:
    """Decode an I/O report or a device-status report.

    Each I/O report sets every input field; fields unused by the reported work
    mode are None. Trigger-mode reports contain alarm flags rather than
    measurements and are returned empty.
    """
    if f_port == 5:
        if len(data) != 7 or not 1 <= data[0] <= 0x0F:
            raise ValueError("Invalid LT-22222-L status report")
        return DecodedPayload(metadata={"firmware_version": version(data[2], data[3])})
    if f_port != 2:
        return DecodedPayload()
    if len(data) != 11:
        raise ValueError("Invalid LT-22222-L frame length")
    mode = data[10] & 0x3F
    if not 1 <= mode <= 5:
        return DecodedPayload()
    status = data[8]
    values: dict[str, Value] = {
        "mode": mode,
        "relay_1": bool(status & 0x80),
        "relay_2": bool(status & 0x40),
        "digital_output_1": bool(status & 0x01),
        "digital_output_2": bool(status & 0x02),
        "voltage_count": unsigned(data[4:8]) if mode == 4 else None,
    }
    for channel in CHANNELS:
        values[f"digital_input_{channel}"] = (
            bool(status & (0x04 << channel)) if mode == 1 else None
        )
        values[f"voltage_{channel}"] = (
            signed(data[2 * channel - 2 : 2 * channel], 1000)
            if mode in (1, 5)
            else None
        )
    values["current_1"] = signed(data[4:6], 1000) if mode in (1, 3, 5) else None
    values["current_2"] = signed(data[6:8], 1000) if mode in (1, 3) else None
    values["digital_count_1"] = (
        unsigned(data[0:4])
        if mode in (2, 3, 4)
        else unsigned(data[6:8])
        if mode == 5
        else None
    )
    values["digital_count_2"] = unsigned(data[4:8]) if mode == 2 else None
    return DecodedPayload(values)


def decode_lwl02(f_port: int, data: bytes) -> DecodedPayload:
    """Decode an LWL02 water leak report."""
    if f_port != 10:
        return DecodedPayload()
    if len(data) < 3:
        raise ValueError("Truncated contact sensor data")
    if data[2] not in (LWL02_MODE, 3):
        raise ValueError("Unexpected work mode")
    if len(data) not in ((9, 10) if data[2] == LWL02_MODE else (10,)):
        raise ValueError("Invalid contact sensor frame length")
    counters = data[2] == LWL02_MODE
    return DecodedPayload(
        {
            "active": bool(data[0] & LWL02_STATUS_MASK),
            "battery_voltage": (unsigned(data[:2]) & 0x3FFF) / 1000,
            "alarm": bool(data[9] & 1) if len(data) == 10 else None,
            "event_count": unsigned(data[3:6]) if counters else None,
            "last_duration": unsigned(data[6:9]) if counters else None,
        }
    )
