"""Compare the Python decoders with the pinned Dragino JavaScript codecs."""

from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

import pytest

from dragino_lorawan import CPL03LB, LDS02, LHT65, LT22222, LWL02, DraginoDevice

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures/reference.json").read_text(encoding="utf-8")
)
MODELS: dict[str, type[DraginoDevice]] = {
    "LHT65": LHT65,
    "LDS02": LDS02,
    "LWL02": LWL02,
    "LT22222": LT22222,
    "CPL03LB": CPL03LB,
}


def same(value: Any) -> Any:
    return value


def equals(expected: str) -> Callable[[Any], bool]:
    return lambda value: value == expected


# Reference key -> (our key, converter). Every reference key must be mapped
# or explicitly ignored, so codec updates cannot silently add fields.
MAPPINGS: dict[str, dict[str, tuple[str, Callable[[Any], Any]]]] = {
    "LHT65": {
        "TempC_SHT": ("temperature", same),
        "Hum_SHT": ("humidity", same),
        "BatV": ("battery_voltage", same),
        "Bat_status": ("reported_battery_status", same),
        "TempC_DS": ("external_temperature", same),
        "No_connect": ("external_sensor_disconnected", lambda _: True),
        "Exti_pin_level": ("external_input", equals("High")),
        "Exti_status": ("external_interrupt", equals("True")),
        "ILL_lx": ("illuminance", same),
        "ADC_V": ("external_voltage", same),
        "Exit_count": ("external_count", same),
    },
    "LDS02": {
        "BAT_V": ("battery_voltage", same),
        "DOOR_OPEN_STATUS": ("active", bool),
        "DOOR_OPEN_TIMES": ("event_count", same),
        "LAST_DOOR_OPEN_DURATION": ("last_duration", same),
        "ALARM": ("alarm", bool),
    },
    "LWL02": {
        "BAT_V": ("battery_voltage", same),
        "WATER_LEAK_STATUS": ("active", bool),
        "WATER_LEAK_TIMES": ("event_count", same),
        "LAST_WATER_LEAK_DURATION": ("last_duration", same),
        "ALARM": ("alarm", bool),
    },
    "LT22222": {
        "RO1_status": ("relay_1", equals("ON")),
        "RO2_status": ("relay_2", equals("ON")),
        # The codec reports a set output bit as a low level.
        "DO1_status": ("digital_output_1", equals("L")),
        "DO2_status": ("digital_output_2", equals("L")),
        "DI1_status": ("digital_input_1", equals("H")),
        "DI2_status": ("digital_input_2", equals("H")),
        "AVI1_V": ("voltage_1", same),
        "AVI2_V": ("voltage_2", same),
        "ACI1_mA": ("current_1", same),
        "ACI2_mA": ("current_2", same),
        "Count1_times": ("digital_count_1", same),
        "Count2_times": ("digital_count_2", same),
        "Acount_times": ("voltage_count", same),
        "FIRMWARE_VERSION": ("firmware_version", same),
    },
    "CPL03LB": {
        "WORKMOD": ("work_mode", str.lower),
        "CMOD": ("counts_are_cumulative", equals("SUM")),
        "ALARM": ("alarm", equals("TRUE")),
        "PIN_STATUS": ("contact_open", equals("OPEN")),
        "TOTAL_PULSE": ("pulse_count", same),
        "LAST_DURATION": ("last_duration", same),
        "PA8_TOTAL_PULSE": ("pa8_count", same),
        "PA4_TOTAL_PULSE": ("pa4_count", same),
        "PB15_TOTAL_PULSE": ("pb15_count", same),
        "EXTI_PA8_Status": ("pa8_open", equals("OPEN")),
        "EXTI_PA4_Status": ("pa4_open", equals("OPEN")),
        "EXTI_PB15_Status": ("pb15_open", equals("OPEN")),
        "FIRMWARE_VERSION": ("firmware_version", same),
        "BAT": ("battery_voltage", same),
    },
}
IGNORED = {
    "LHT65": {"Ext_sensor", "Work_mode", "Systimestamp"},
    "LDS02": {"Node_type", "MOD", "WATER_LEAK_STATUS"},
    "LWL02": {"Node_type", "MOD", "DOOR_OPEN_STATUS"},
    "LT22222": {
        "Hardware_mode",
        "Work_mode",
        "First_status",
        "DO3_status",
        "DI3_status",
        "FREQUENCY_BAND",
        "SUB_BAND",
        "TDC_sec",
    },
    "CPL03LB": {
        "Node_type",
        "TDC",
        "TTRIG_MOD",
        "TIME",
        "CALCULATE_FLAG",
        "PA8_ROC",
        "PA4_ROC",
        "PB15_ROC",
        "EXTI_PA8_Trigger",
        "EXTI_PA4_Trigger",
        "EXTI_PB15_Trigger",
        "SENSOR_MODEL",
        "FREQUENCY_BAND",
        "SUB_BAND",
    },
}


@pytest.mark.parametrize(
    "case",
    FIXTURES,
    ids=[f"{case['family']}-{case['f_port']}-{case['name']}" for case in FIXTURES],
)
def test_matches_reference_codec(case: dict[str, Any]) -> None:
    """Decoded values agree with the vendor codec for every mapped field."""
    model = MODELS[case["family"]]
    data = bytes.fromhex(case["payload"])
    expected = case["expected"]

    if expected and "errors" in expected:
        with pytest.raises(ValueError):
            model.decode(case["f_port"], data)
        return

    decoded = model.decode(case["f_port"], data)
    actual = {**decoded.values, **decoded.metadata}
    if expected is None:
        assert actual == {}
        return

    reference = expected["data"]
    unknown = reference.keys() - MAPPINGS[case["family"]].keys()
    assert unknown <= IGNORED[case["family"]]
    for key, value in reference.items():
        if key not in MAPPINGS[case["family"]]:
            continue
        name, convert = MAPPINGS[case["family"]][key]
        assert actual[name] == pytest.approx(convert(value)), key
