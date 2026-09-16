"""Read XBee telemetry and plot latitude, longitude, and altitude in 3D."""

from __future__ import annotations

import argparse  # Reads the serial port and baud rate from the command line.
import csv  # Parses the comma-separated telemetry packet.
import math  # Generates the test path in simulation mode.
import queue  # Safely passes packets from XBee callbacks to the plot.
import threading  # Reads Arduino serial data without blocking the graph.
from dataclasses import dataclass

import matplotlib.pyplot as plt  # Draws the live 3D graph.
from digi.xbee.devices import XBeeDevice  # Digi's XBee3 interface.
from matplotlib.animation import FuncAnimation  # Calls the update function.
import serial  # Reads telemetry forwarded by an Arduino over USB.


@dataclass(frozen=True)
class Telemetry:
    """The ten values expected in one telemetry packet."""

    # Packet order: Timestamp, State, Temperature, Pressure, Altitude,
    # Battery Voltage, Battery Current, Latitude, Longitude, Prev_CMD_echo.
    timestamp: int
    state: int
    temperature: float
    pressure: float
    altitude: float
    battery_voltage: float
    battery_current: float
    latitude: float
    longitude: float
    prev_cmd_echo: str


def make_simulated_telemetry(frame: int) -> Telemetry:
    """Create one moving test sample when no XBee is connected."""
    angle = frame / 10
    return Telemetry(
        timestamp=frame,
        state=1,
        temperature=22.0,
        pressure=1013.25,
        altitude=100.0 + 10.0 * math.sin(angle),
        battery_voltage=7.4,
        battery_current=0.8,
        latitude=18.5204 + 0.001 * math.cos(angle),
        longitude=73.8567 + 0.001 * math.sin(angle),
        prev_cmd_echo="SIM",
    )


def parse_telemetry(payload: str) -> Telemetry:
    """Convert one decoded CSV packet into typed telemetry values."""
    # csv.reader handles whitespace and quoted text in the final command field.
    fields = next(csv.reader([payload.strip()]))
    if len(fields) != 10:
        raise ValueError(f"expected 10 fields, received {len(fields)}")

    # Convert each field to the type described by the telemetry protocol.
    return Telemetry(
        timestamp=int(fields[0].strip()),
        state=int(fields[1].strip()),
        temperature=float(fields[2].strip()),
        pressure=float(fields[3].strip()),
        altitude=float(fields[4].strip()),
        battery_voltage=float(fields[5].strip()),
        battery_current=float(fields[6].strip()),
        latitude=float(fields[7].strip()),
        longitude=float(fields[8].strip()),
        prev_cmd_echo=fields[9].strip(),
    )


def add_queued_samples(
    telemetry_queue: queue.Queue[Telemetry],
    longitudes: list[float],
    latitudes: list[float],
    altitudes: list[float],
) -> None:
    """Move all waiting samples into the lists used by the plot."""
    while True:
        try:
            sample = telemetry_queue.get_nowait()
        except queue.Empty:
            return

        longitudes.append(sample.longitude)
        latitudes.append(sample.latitude)
        altitudes.append(sample.altitude)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "port", nargs="?", default="COM5",
        help="XBee serial port (default: COM5)")
    parser.add_argument("--baud", type=int, default=9600,
                        help="XBee baud rate (default: 9600)")
    parser.add_argument(
        "--arduino", action="store_true",
        help="read newline-terminated telemetry from an Arduino USB port")
    parser.add_argument(
        "--simulate", action="store_true",
        help="plot generated telemetry without connecting to an XBee")
    args = parser.parse_args()

    if not args.simulate and args.port is None:
        parser.error("port is required unless --simulate is used")

    # XBee callbacks run in the background. The graph reads this queue from its
    # timer, so Matplotlib itself is updated only on the graph's thread.
    telemetry_queue: queue.Queue[Telemetry] = queue.Queue()
    device = None
    arduino_serial = None
    stop_reader = threading.Event()

    def handle_payload(raw_data: bytes) -> None:
        """Decode, parse, and queue one telemetry packet."""
        try:
            payload = raw_data.decode("utf-8").strip()
            if not payload:
                return
            print(f"Received: {payload!r}")
            sample = parse_telemetry(payload)
            print(
                f"Position: lat={sample.latitude}, "
                f"lon={sample.longitude}, alt={sample.altitude}")
            telemetry_queue.put(sample)
        except (UnicodeDecodeError, ValueError) as error:
            print(f"Ignoring packet: {error}")

    def on_data_received(message) -> None:
        """Handle a packet delivered by the Digi XBee callback."""
        handle_payload(message.data)

    # Direct XBee USB adapters use Digi's XBeeDevice API.
    if not args.simulate and not args.arduino:
        device = XBeeDevice(args.port, args.baud)
        device.open()
        device.add_data_received_callback(on_data_received)
        print(
            f"Listening for XBee telemetry on {args.port} at {args.baud} baud...")

    # An Arduino USB connection carries ordinary serial text, not XBee frames.
    if args.arduino:
        arduino_serial = serial.Serial(args.port, args.baud, timeout=1)

        def read_arduino() -> None:
            while not stop_reader.is_set():
                raw_data = arduino_serial.readline()
                if raw_data:
                    handle_payload(raw_data)

        threading.Thread(target=read_arduino, daemon=True).start()
        print(
            f"Listening for Arduino telemetry on {args.port} at {args.baud} baud...")

    # These lists contain the values displayed by the 3D line.
    longitudes: list[float] = []
    latitudes: list[float] = []
    altitudes: list[float] = []

    if args.simulate:
        # Seed the graph so it is visible before the first timer update.
        longitudes.append(73.8567)
        latitudes.append(18.5214)
        altitudes.append(100.0)

    # Graph coordinates: longitude (X), latitude (Y), altitude (Z).
    figure = plt.figure("XBee3 Telemetry")
    axes = figure.add_subplot(111, projection="3d")
    line, = axes.plot(
        longitudes, latitudes, altitudes, marker="o", linewidth=1)
    axes.set_xlabel("Longitude")
    axes.set_ylabel("Latitude")
    axes.set_zlabel("Altitude")
    axes.set_title(
        "Simulated Telemetry" if args.simulate else "Live XBee3 Telemetry")
    if args.simulate:
        axes.set_xlim(73.855, 73.858)
        axes.set_ylim(18.519, 18.522)
        axes.set_zlim(85, 115)

    def update(_frame):
        if args.simulate:
            telemetry_queue.put(make_simulated_telemetry(_frame))

        add_queued_samples(
            telemetry_queue, longitudes, latitudes, altitudes)

        if longitudes:
            line.set_data(longitudes, latitudes)
            line.set_3d_properties(altitudes)
            axes.relim()
            axes.autoscale_view()
        return (line,)

    def close(_event) -> None:
        stop_reader.set()
        if arduino_serial is not None and arduino_serial.is_open:
            arduino_serial.close()
        if device is not None and device.is_open():
            device.close()

    figure.canvas.mpl_connect("close_event", close)
    animation = FuncAnimation(
        figure, update, interval=100, blit=False, cache_frame_data=False)

    try:
        plt.show()
    finally:
        stop_reader.set()
        if arduino_serial is not None and arduino_serial.is_open:
            arduino_serial.close()
        if device is not None and device.is_open():
            device.close()
        del animation


if __name__ == "__main__":
    main()
