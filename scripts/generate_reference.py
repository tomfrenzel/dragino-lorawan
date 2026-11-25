"""Regenerate reference fixtures from the pinned Dragino JavaScript codecs."""

import argparse
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "chirpstack", type=Path, help="chirpstack/chirpstack-device-profiles checkout"
)
parser.add_argument(
    "lorawan_devices", type=Path, help="TheThingsNetwork/lorawan-devices checkout"
)
args = parser.parse_args()
sources = {
    "LHT65": args.lorawan_devices / "vendor/dragino/lht65.js",
    "LDS02": args.chirpstack / "vendors/dragino/codecs/lds02.js",
    "LWL02": args.chirpstack / "vendors/dragino/codecs/lwl02.js",
    "LT22222": args.chirpstack / "vendors/dragino/codecs/lt-22222-l.js",
    "CPL03LB": args.chirpstack / "vendors/dragino/codecs/cpl03-lb.js",
}
cases = []


def add(family: str, f_port: int, payload: str, name: str) -> None:
    cases.append(
        {
            "family": family,
            "f_port": f_port,
            "payload": payload,
            "name": name,
            "source": str(sources[family].resolve()),
        }
    )


for payload, name in (
    ("cbf60b0d0376010add7fff", "ttn-example"),
    ("cbeaff9c026d01ff387fff", "negative-probe"),
    ("cbf6fc1803760000000000", "negative-no-probe"),
    ("0bf60b0d0376040100ffff", "interrupt"),
    ("cbf60b0d03760500647fff", "illuminance"),
    ("cbf60b0d0376060bb87fff", "adc"),
    ("cbf60b0d0376070102ffff", "count-16"),
    ("cbf60b0d03760801020304", "count-32"),
    ("ff9c0b0d43760900000000", "probe-and-timestamp"),
    ("cbea0105026d4101aa7fff", "datalog"),
):
    add("LHT65", 2, payload, name)
for payload, name in (
    ("8bd00100000500000701", "open-alarm"),
    ("0bd00100ffff00001e00", "closed"),
    ("cbd00300000000000001", "combined"),
):
    add("LDS02", 10, payload, name)
for payload, name in (
    ("4bd00200000300000400", "leak"),
    ("0bd002ffffff00001e00", "dry"),
    ("4bd00300000000000000", "combined"),
):
    add("LWL02", 10, payload, name)
for f_port, payload, name in (
    (2, "05dcff060fa04e208a0041", "mode-1"),
    (2, "05dcff060fa04e20750001", "mode-1-lt33222"),
    (2, "0000000a0000000bc00042", "mode-2"),
    (2, "ffffffff00000001000042", "mode-2-max"),
    (2, "000000070fa0ff9c010043", "mode-3"),
    (2, "00000009000000204a0044", "mode-4"),
    (2, "05dc07d00fa0002a020045", "mode-5"),
    (5, "01ff0160000258", "status-manual"),
    (5, "0208f2ab0004b0", "status-two-digit"),
    (5, "0fff0161000258", "status-as923-4"),
):
    add("LT22222", f_port, payload, name)
for f_port, payload, name in (
    (2, "37ffffff010203ffffffff", "single-max"),
    (2, "0000000200003c00000000", "single"),
    (6, "3f800000ffffff01020305", "counters-roc"),
    (6, "08000005000006ffffff", "counters"),
    (7, "19", "interrupt"),
    (7, "26ffffffffffffffffffff", "interrupt-padded"),
    (5, "20011101ff0b45", "status"),
    (5, "20011102030e10", "status-sub-band"),
    (2, "00000002000000000000", "error-short"),
    (2, "0800000200003c00000000", "error-mode"),
    (6, "000000050000060000ff", "error-mode"),
    (5, "21011101ff0b45", "error-model"),
    (5, "20011100ff0b45", "error-band"),
    (7, "", "error-empty"),
):
    add("CPL03LB", f_port, payload, name)

proc = subprocess.run(
    ["node", str(Path(__file__).with_name("reference.cjs"))],
    input="\n".join(json.dumps(case) for case in cases),
    text=True,
    capture_output=True,
    check=True,
)
out = [json.loads(line) for line in proc.stdout.splitlines()]
(Path(__file__).resolve().parents[1] / "tests/fixtures/reference.json").write_text(
    json.dumps(out, indent=2) + "\n", newline="\n"
)
print("Generated", len(out), "cases")
for case in out:
    if "error" in case:
        print("ERROR", case["family"], case["name"], case["error"])
