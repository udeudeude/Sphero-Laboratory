# Sphero Laboratory

Experimental local-network controller for **Sphero 2.0** and **SPRK+**. The Mac runs a Python Bluetooth bridge and serves a touchscreen web interface to an iPhone. Intended to evolve into synchronized robotics, choreography and SuperCollider control.

**Status: software prototype; physical dual-robot control is not yet verified.** In particular, Sphero 2.0 uses Bluetooth Classic, whereas the `spherov2` scanner uses BLE. The app now has an **experimental legacy serial/RFCOMM adapter** for Sphero 2.0, alongside BLE for SPRK+, but simultaneous operation still needs testing with real hardware. The user has connected both robots to an iPhone using Sphero's apps, but that does not establish Mac connectivity.

## Run on Mac

Requires macOS, Python 3 and Wi-Fi shared with the iPhone.

1. Download the repository ZIP from GitHub, unzip it, and open Terminal in the extracted directory.
2. Execute `bash START.command`. This builds a local `.venv` and installs the libraries from `requirements.txt` when needed.
3. Open the **complete iPhone URL printed by Terminal**, including its unique `?token=...` parameter. The app saves the token for that browser tab and removes it from the address bar.
4. Close Sphero Play/Edu, wake the robots, press **Scan for robots** and test one connection at a time.
5. Put the robots on the floor, start with a low maximum speed, and press **STOP BOTH** to stop.
6. Keep the bridge running on the Mac. Use Control-C in Terminal to shut it down.

The file `START.command` may not have executable permissions when downloaded as a ZIP. `bash START.command` works without changing permissions. To double-click in Finder later, run `chmod +x START.command` once. If macOS blocks it, right-click and choose Open.

### Checking for the Sphero 2.0 serial port

Pair the **Sphero 2.0** with your Mac in Bluetooth settings, disconnect Sphero Play/Edu on the iPhone, and try:

```sh
ls /dev/cu.* | grep -i sphero
```

If you see a device such as `/dev/cu.Sphero-XYZ`, the bridge should offer it on the next scan as a **Classic RFCOMM (experimental)** candidate. If no serial port appears, this transport cannot connect yet. For a nonstandard serial name, set `SPHERO_CLASSIC_PORT=/dev/cu.YOUR-PORT` before launching the bridge; only use a port you recognize as belonging to the robot.

The classic transport uses the original Sphero API v1 roll and RGB commands, with no response acknowledgment. Opening the port or sending a command therefore **does not prove that the robot received it**. Test slowly and monitor the robot physically.

### Demo without robots

After the venv exists, run:

```sh
SPHERO_DEMO=1 .venv/bin/python server.py
```

The browser can scan for two simulated devices, connect each, select drive modes, set heading offsets and issue commands without Bluetooth hardware.

### Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile server.py
bash -n START.command
```

The unit tests do not need any third-party dependencies or robots.

## Controls

- Synchronized, mirrored, A-only and B-only driving.
- Touch joystick (or arrow keys on desktop).
- Independent heading offsets, saved in the browser.
- Speed limiting (starts at 25%).
- LED presets.
- Explicit two-robot stop.
- Server-side inactivity watchdog, currently 0.75 seconds. It attempts to stop motion if input stops, **but cannot guarantee stopping if the Bluetooth stack or hardware is unresponsive**.
- Diagnostics for scans, connection failures and command errors.

## Security

The bridge listens on all Mac network interfaces so the iPhone can reach it. Its API requires a random session token shown in the Terminal URL. Keep that URL private and **use only a trusted local network**: the transport is HTTP, not HTTPS. Do not port-forward or expose port 8765 publicly. Re-starting the server rotates the token unless `SPHERO_TOKEN` is explicitly provided.

## Hardware status and limitations

1. **SPRK+:** BLE scanning and `SpheroEduAPI` communication are implemented but need live tests on the user's Mac.
2. **Sphero 2.0:** An experimental Bluetooth Classic serial transport is implemented in `legacy_serial.py` using Sphero API v1 packets. It appears in Scan **only if macOS provides a serial port matching `/dev/cu.Sphero*` or `/dev/tty.Sphero*`**. It has not been tested with the physical robot. Modern macOS may not create such a port.
3. **Simultaneous control:** Software supports one serial Classic robot and one BLE robot with a combined control command. Real simultaneous Bluetooth connections have not been demonstrated.
4. **Control orientation:** Two robots may have different notions of 'forward'. Independently aim or offset them.
5. **Safety:** The emergency stop is a software command and may fail after Bluetooth loss. Use an open, unobstructed testing space.

## Development backlog

- [x] Import project source to GitHub.
- [x] Replace short timed rolls with continuous heading + speed.
- [x] Preserve discovered robot identities through connection.
- [x] Add server-side motion watchdog and safe speed defaults.
- [x] Add local-network API authentication and request validation.
- [x] Isolated Python installer, demo mode and automated unit tests.
- [x] Heading offsets, diagnostics and keyboard driving.
- [ ] Verify BLE discovery, pairing, movement and lights on SPRK+.
- [x] Implement an experimental RFCOMM serial adapter for Sphero 2.0, with protocol-level tests.
- [ ] Establish an actual Sphero 2.0 serial connection and validate movement on macOS 12+.
- [ ] Verify both Bluetooth links remain up simultaneously.
- [ ] Confirm live hardware stop and watchdog behavior, including dropped Wi-Fi.
- [ ] Improve per-robot sensor and battery telemetry.
- [ ] Add saved paths and choreography editor, avoiding uncontrolled motion.
- [ ] Add external event input / SuperCollider OSC routing.
- [ ] Add browser UI tests and verify iPhone Safari layout.
- [ ] Optional native iOS bridge for Mac-free use.

### Acknowledgment

Uses the community-maintained [spherov2 Python library](https://github.com/artificial-intelligence-class/spherov2.py). Not affiliated with Sphero.
