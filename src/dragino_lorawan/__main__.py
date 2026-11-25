"""Discover Dragino devices and print their readings."""

from lorawan_connection.cli_helper import run

from . import DraginoDevices


def main() -> None:
    """Run the Dragino command-line interface."""
    run(DraginoDevices.DEVICES)


if __name__ == "__main__":
    main()
