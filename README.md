# Sphero Laboratory

Experimental iPhone-friendly control surface for Sphero 2.0 and SPRK+ using a macOS Bluetooth bridge.

## Status

Early hardware-testing prototype. Simultaneous Bluetooth connections and driving are **not yet verified on physical robots**.

## Project files

The initial v0.1 prototype includes a Python bridge (`server.py`), browser interface (`static/index.html`), and a Mac launcher (`START.command`). These files are being staged for version control.

## Next milestones

1. Import the v0.1 source files.
2. Verify discovery and connection of each robot on macOS.
3. Test emergency stop, separate driving, and concurrent driving.
4. Improve diagnostics, safety, mobile UI, and documentation.
5. Add programmable choreography and SuperCollider integration.
