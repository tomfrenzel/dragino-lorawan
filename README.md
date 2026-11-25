# Dragino LoRaWAN

Read and control Dragino devices through ChirpStack or The Things Stack using
[`lorawan-connection`](https://github.com/home-assistant-libs/lorawan-connection).

This library powers the
[Dragino LoRaWAN Home Assistant integration](https://github.com/tomfrenzel/home-assistant-dragino-lorawan).

| Model | Readings | Commands | Automatic discovery |
| --- | --- | --- | --- |
| LT-22222-L | Relays, digital outputs/inputs, voltages, currents, counters, firmware | Set relay, set digital output | ChirpStack, TTS |
| LDS02 | Door state, open alarm, event count, last opening duration, battery | — | ChirpStack, TTS |
| LWL02 | Water leak, alarm, event count, last leak duration, battery | Reporting interval, reset count | ChirpStack, TTS |
| LHT65 | Temperature, humidity, battery, external probe readings | — | TTS |
| CPL03-LB | Single contact/alarm, three pulse counters or contact inputs, durations, battery, firmware | Request device status | ChirpStack, TTS |

Every model also exposes `rssi` and `snr` from the strongest gateway reception of
the latest uplink, when the connection reports gateway metadata.

Raw payloads are decoded locally; a server-side payload formatter is not required.
Devices are matched by their catalog identity (ChirpStack vendor 676 or TTS brand
`dragino`), so custom profiles are not discovered automatically.

## Command-line reader

The `dragino-lorawan` command lists devices or prints readings as they arrive.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) to run it with
`uvx`, or use `pip install "dragino-lorawan[chirpstack]"` for ChirpStack and
`pip install "dragino-lorawan[tts]"` for The Things Stack.

### ChirpStack

Use a ChirpStack v4 gRPC endpoint, an API key, and the tenant UUID.

```sh
export CHIRPSTACK_API_KEY="your-api-key"
uvx --from "dragino-lorawan[chirpstack]" dragino-lorawan \
  --backend chirpstack \
  --server https://chirpstack.example.com:8080 \
  --tenant YOUR_TENANT_UUID \
  --application YOUR_APPLICATION_UUID
```

### The Things Stack

Use the Application Server gRPC endpoint and an application API key with device
read and application traffic read rights.

```sh
export TTS_API_KEY="your-api-key"
uvx --from "dragino-lorawan[tts]" dragino-lorawan \
  --backend tts \
  --server https://eu1.cloud.thethings.network:8884 \
  --identity-server https://eu1.cloud.thethings.network:8884 \
  --application YOUR_APPLICATION_ID
```

Add `--list` to print the current devices and exit, or `--json` for newline-delimited
JSON output. Run `dragino-lorawan --help` for all options.
`python -m dragino_lorawan` also works.

## Python

```python
from lorawan_connection.backend.chirpstack import ChirpStackConnection
from dragino_lorawan import LT22222, DraginoDevices


async def switch_relay(
    endpoint: str, api_key: str, tenant: str, application: str
) -> None:
    connection = ChirpStackConnection(
        endpoint,
        api_key,
        tenant_id=tenant,
        application_ids=[application],
        network_id=endpoint,
    )
    devices = DraginoDevices(connection)
    try:
        await connection.async_connect()
        await devices.async_setup()
        for device in devices.devices.values():
            print(device.descriptor.name, device.model_name)
            if isinstance(device, LT22222):
                await device.async_set_relay(1, True)
    finally:
        devices.close()
        await connection.close()
```

The collection also accepts a `TTSConnection`. Subscribe with
`devices.subscribe_device_added(listener)` and `device.add_update_listener(listener)`
to receive live readings. Values remain `None` until the device reports them.

### Reading values

Model properties such as `LHT65.temperature`, `LDS02.active`, and
`LT22222.relays` remain available. All models also expose the latest decoded
`values` and device `metadata` (such as `firmware_version`) as dictionaries, and
`device.value(name)` reads a single value.

Every model has a `decode(f_port, data)` class method that decodes a raw payload
without a connection and returns a `DecodedPayload`:

```python
from dragino_lorawan import LHT65

payload = LHT65.decode(2, bytes.fromhex("cbf60b0d0376010add7fff"))
print(payload.values["temperature"], payload.values["external_temperature"])
# 28.29 27.81
```

Direct decoding raises `ValueError` for malformed frames. Configuration, datalog,
and other non-measurement frames decode to an empty payload. Live models discard
malformed payloads atomically. Partial updates retain other readings, and older
uplinks cannot replace newer values. Absent or disconnected readings are `None`.

Downlink commands require an API key with downlink write permission. LT-22222-L
relay and digital-output commands wait for acknowledgement; LWL02 and CPL03-LB
commands are queued for the device's next receive window.

## Development

All payload decoders live in `src/dragino_lorawan/decoders.py`, with separate
functions for LHT65, LDS02, LWL02, CPL03-LB, and LT-22222-L. Live device
handling remains in `device.py`, model properties and commands in `models.py`,
and the shared decoded payload types in `payload.py`.

```sh
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv build
```

Tests include reference outputs from the vendor JavaScript codecs for every
decoder family, and malformed, partial, and out-of-order messages.
See [fixture provenance and regeneration](tests/fixtures/README.md).

## License

Apache-2.0. See [NOTICE](NOTICE) for attribution.
