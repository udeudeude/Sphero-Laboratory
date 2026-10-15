"""Experimental Sphero 2.0 Bluetooth Classic serial transport (Sphero API v1).

Requires a macOS RFCOMM serial device, usually /dev/cu.Sphero*, and pyserial.
Packet framing follows Orbotix Sphero API v1.20. No hardware tests yet.
"""
from pathlib import Path
import glob
import os


def classic_ports():
    """Find plausible classic Sphero serial devices without opening them."""
    explicit = os.environ.get('SPHERO_CLASSIC_PORT', '').strip()
    ports = [explicit] if explicit else []
    for pattern in ('/dev/cu.Sphero*', '/dev/tty.Sphero*', '/dev/cu.sphero*', '/dev/tty.sphero*'):
        ports.extend(glob.glob(pattern))
    return list(dict.fromkeys(port for port in ports if port and Path(port).exists()))


def packet(did, cid, sequence, payload=()):
    data = bytes(payload)
    if len(data) > 254:
        raise ValueError('Payload too large')
    frame = bytes((0xff, 0xfe, did, cid, sequence & 0xff, len(data) + 1)) + data
    return frame + bytes((~sum(frame[2:]) & 0xff,))


class LegacySphero:
    """Subset of SpheroEduAPI used by the web bridge, backed by RFCOMM serial."""
    def __init__(self, path, serial_factory=None):
        if serial_factory is None:
            import serial
            serial_factory = serial.Serial
        self.conn = serial_factory(port=path, baudrate=115200, timeout=0.25, write_timeout=0.5)
        self.seq = 0
        self.heading = 0
        self.speed = 0
        self.closed = False

    def _send(self, did, cid, data):
        if self.closed:
            raise RuntimeError('Legacy Sphero connection closed')
        frame = packet(did, cid, self.seq, data)
        self.seq = (self.seq + 1) & 0xff
        if self.conn.write(frame) != len(frame):
            raise IOError('Incomplete Sphero Classic serial write')

    def _roll(self, enabled=True):
        self._send(0x02, 0x30, [self.speed, self.heading >> 8, self.heading & 0xff, int(enabled)])

    def set_heading(self, heading):
        self.heading = int(heading) % 360

    def set_speed(self, speed):
        self.speed = max(0, min(255, int(speed)))
        self._roll(self.speed > 0)

    def set_main_led(self, color):
        self._send(0x02, 0x20, [color.r, color.g, color.b, 0])

    def close(self):
        if not self.closed:
            try:
                self.set_speed(0)
            finally:
                self.closed = True
                self.conn.close()
