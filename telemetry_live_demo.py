"""Live telemetry graph with simulation, Digi XBee, and Arduino modes."""

from __future__ import annotations

import argparse
import csv
import math
import queue
import threading
from dataclasses import dataclass

import matplotlib.pyplot as plt
from digi.xbee.devices import XBeeDevice
from matplotlib.animation import FuncAnimation
import serial


@dataclass(frozen=True)
class Telemetry:
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


def parse_telemetry(payload: str) -> Telemetry:
    """Parse one ten-field comma-separated telemetry packet."""
    fields = next(csv.reader([payload.strip()]))
    if len(fields) != 10:
        raise ValueError(f"expected 10 fields, received {len(fields)}")
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


def simulated_sample(frame: int) -> Telemetry:
    """Create a moving sample for testing without hardware."""
    angle = frame / 10.0
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", nargs="?",
                        help="serial port, for example COM5")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--arduino", action="store_true")
    parser.add_argument("--xbee", action="store_true")
    parser.add_argument("--simulate", action="store_true")
    args = parser.parse_args()

    # No arguments means a visible demo, so the graph is never empty during testing.
    simulation = args.simulate or (
        args.port is None and not args.arduino and not args.xbee)
    port = args.port or "COM5"
    samples: queue.Queue[Telemetry] = queue.Queue()
    device = None
    serial_port = None
    stop_reader = threading.Event()

    def accept_payload(raw_data: bytes) -> None:
        try:
            payload = raw_data.decode("utf-8").strip()
            if not payload:
                return
            sample = parse_telemetry(payload)
            print(
                f"Received position: lat={sample.latitude}, "
                f"lon={sample.longitude}, alt={sample.altitude}",
                flush=True,
            )
            samples.put(sample)
        except (UnicodeDecodeError, ValueError) as error:
            print(f"Ignoring packet: {error}", flush=True)

    if not simulation and args.xbee:
        device = XBeeDevice(port, args.baud)
        device.open()
        device.add_data_received_callback(
            lambda message: accept_payload(message.data))
        print(f"Listening for Digi XBee data on {port} at {args.baud} baud")

    if not simulation and args.arduino:
        serial_port = serial.Serial(port, args.baud, timeout=1)

        def read_arduino() -> None:
            while not stop_reader.is_set():
                raw_data = serial_port.readline()
                if raw_data:
                    accept_payload(raw_data)

        threading.Thread(target=read_arduino, daemon=True).start()
        print(f"Listening for Arduino data on {port} at {args.baud} baud")

    longitudes: list[float] = []
    latitudes: list[float] = []
    altitudes: list[float] = []

    figure = plt.figure("Telemetry 3D Graph")
    axes = figure.add_subplot(111, projection="3d")
    line, = axes.plot([], [], [], marker="o", linewidth=1)
    axes.set_xlabel("Longitude")
    axes.set_ylabel("Latitude")
    axes.set_zlabel("Altitude")
    axes.set_title("Simulated Telemetry" if simulation else "Live Telemetry")
    axes.set_box_aspect((1, 1, 0.8))

    def update_axis_limits() -> None:
        """Fit each axis to the data while keeping a visible minimum span."""
        def limits(values: list[float], minimum_span: float) -> tuple[float, float]:
            low = min(values)
            high = max(values)
            span = max(high - low, minimum_span)
            center = (low + high) / 2.0
            return center - span * 0.6, center + span * 0.6

        axes.set_xlim(*limits(longitudes, 0.001))
        axes.set_ylim(*limits(latitudes, 0.001))
        axes.set_zlim(*limits(altitudes, 10.0))

    def update(frame: int):
        if simulation:
            samples.put(simulated_sample(frame))
        while True:
            try:
                sample = samples.get_nowait()
            except queue.Empty:
                break
            longitudes.append(sample.longitude)
            latitudes.append(sample.latitude)
            altitudes.append(sample.altitude)
        if longitudes:
            line.set_data(longitudes, latitudes)
            line.set_3d_properties(altitudes)
            update_axis_limits()
        return line,

    def close(_event) -> None:
        stop_reader.set()
        if serial_port is not None and serial_port.is_open:
            serial_port.close()
        if device is not None and device.is_open():
            device.close()

    figure.canvas.mpl_connect("close_event", close)
    animation = FuncAnimation(
        figure, update, interval=100, blit=False, cache_frame_data=False)
    try:
        plt.show()
    finally:
        close(None)
        del animation


if __name__ == "__main__":
    main()
