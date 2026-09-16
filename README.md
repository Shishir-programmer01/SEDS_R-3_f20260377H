# SEDS Janus Telemetry Ground Control

Python ground-control telemetry viewer for the SEDS Janus team. It parses the
ten-field telemetry packet and plots longitude, latitude, and altitude on a
live 3D graph.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Simulation

Run without hardware:

```powershell
.\.venv\Scripts\python.exe .\xbee_telemetry_3d.py --simulate
```

## Arduino USB serial

Use this mode when the Arduino forwards one complete telemetry packet per
line over USB:

```powershell
.\.venv\Scripts\python.exe .\xbee_telemetry_3d.py COM5 --baud 9600 --arduino
```

Replace `COM5` with the port shown for the Arduino. The Arduino output must
contain exactly ten comma-separated fields:

```text
Timestamp,State,Temperature,Pressure,Altitude,BatteryVoltage,BatteryCurrent,Latitude,Longitude,Prev_CMD_echo
```

## Direct XBee USB adapter

For an XBee connected directly through an XBee USB adapter, omit `--arduino`:

```powershell
.\.venv\Scripts\python.exe .\xbee_telemetry_3d.py COM5 --baud 9600
```

The direct XBee mode uses the Digi XBee Python library.