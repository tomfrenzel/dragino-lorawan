# Reference fixtures

`reference.json` contains the output of the vendor JavaScript codecs for the
payloads listed in `scripts/generate_reference.py`. `tests/test_reference.py`
checks that the Python decoders agree with them for every mapped field.

## Sources

| Family | Codec | Repository and commit |
| --- | --- | --- |
| LHT65 | `vendor/dragino/lht65.js` | [TheThingsNetwork/lorawan-devices@1839d95](https://github.com/TheThingsNetwork/lorawan-devices/blob/1839d95018b804d3aa6112786b9a1b31a60efeb2/vendor/dragino/lht65.js) |
| LDS02 | `vendors/dragino/codecs/lds02.js` | [chirpstack/chirpstack-device-profiles@f35a6a0](https://github.com/chirpstack/chirpstack-device-profiles/blob/f35a6a025620109d585e00793864f8eddcbb6806/vendors/dragino/codecs/lds02.js) |
| LWL02 | `vendors/dragino/codecs/lwl02.js` | [chirpstack/chirpstack-device-profiles@f35a6a0](https://github.com/chirpstack/chirpstack-device-profiles/blob/f35a6a025620109d585e00793864f8eddcbb6806/vendors/dragino/codecs/lwl02.js) |
| LT22222 | `vendors/dragino/codecs/lt-22222-l.js` | [chirpstack/chirpstack-device-profiles@f35a6a0](https://github.com/chirpstack/chirpstack-device-profiles/blob/f35a6a025620109d585e00793864f8eddcbb6806/vendors/dragino/codecs/lt-22222-l.js) |
| CPL03LB | `vendors/dragino/codecs/cpl03-lb.js` | [chirpstack/chirpstack-device-profiles@f35a6a0](https://github.com/chirpstack/chirpstack-device-profiles/blob/f35a6a025620109d585e00793864f8eddcbb6806/vendors/dragino/codecs/cpl03-lb.js) |

The TTN copy of the CPL03-LB codec is not used because it is stored with
literal `\n` escapes and does not parse.

## Regenerating

Requires Node.js. Check out both repositories at the commits above, then run:

```sh
python scripts/generate_reference.py path/to/chirpstack-device-profiles path/to/lorawan-devices
```

## Intentional deviations

- Datalog, configuration, probe-ID and trigger-mode frames are not
  measurements and decode to an empty payload.
- Frames rejected by the reference codecs raise `ValueError`.
- LHT65 humidity outside 0–100 % is rejected rather than reported.
- A disconnected LHT65 probe (`0x7FFF`) is reported as `None` instead of
  `327.67`, so the cases avoid it.
- Reference-only fields such as frequency band, uplink interval, and trigger
  flags are listed in `IGNORED` in `tests/test_reference.py`.
