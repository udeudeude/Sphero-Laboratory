#!/usr/bin/env python3
"""Local bridge for the Sphero Laboratory browser controller.

Bluetooth support is experimental. No hardware access occurs in demo mode.
"""
import hmac
import json
import os
import secrets
import socket
import threading
import time
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from legacy_serial import classic_ports, LegacySphero

ROOT = Path(__file__).resolve().parent
PORT = int(os.environ.get('PORT', '8765'))
DEMO = os.environ.get('SPHERO_DEMO') == '1'
DEADMAN_SECONDS = 0.75
TOKEN = os.environ.get('SPHERO_TOKEN') or secrets.token_urlsafe(24)


class Bridge:
    def __init__(self, demo=False, clock=time.monotonic):
        self.demo = demo
        self.clock = clock
        self.lock = threading.RLock()
        self.robots = {}  # slot -> connection
        self.found = {}   # stable scan key -> Toy, retained until next scan
        self.labels = []
        self.last_drive = {}
        self.last_error = None

    def status(self):
        with self.lock:
            return {
                'mode': 'demo' if self.demo else 'hardware',
                'robots': {slot: {'name': item['name'], 'id': item['id']}
                           for slot, item in self.robots.items()},
                'seen': list(self.labels),
                'lastError': self.last_error,
                'watchdogSeconds': DEADMAN_SECONDS,
            }

    def scan(self):
        if self.demo:
            found = [('demo-2', 'Demo Sphero 2.0', 'Demo'),
                     ('demo-sprk', 'Demo SPRK+', 'Demo')]
            toys = {key: None for key, _, _ in found}
        else:
            found, toys = [], {}
            # Sphero 2.0 uses Bluetooth Classic, often exposed as a serial
            # device on older macOS setups. It cannot appear in a BLE scan.
            for path in classic_ports():
                key = 'classic:' + path
                toys[key] = path
                found.append((key, 'Sphero 2.0 · ' + Path(path).name, 'Classic RFCOMM (experimental)'))
            try:
                from spherov2 import scanner
                discovered = scanner.find_toys(timeout=8)
            except Exception as exc:
                if not found:
                    raise RuntimeError('BLE scan failed; no Classic ports found: ' + str(exc)) from exc
                self.last_error = 'BLE scan failed: ' + str(exc)
                discovered = []
            for toy in discovered:
                name = str(getattr(toy, 'name', type(toy).__name__))
                address = str(getattr(toy, 'address', '') or getattr(toy, 'identifier', ''))
                key = f'ble:{name}|{address}'
                if key in toys:
                    key = f'{key}|{len(found)}'
                toys[key] = toy
                found.append((key, name, type(toy).__name__))
        with self.lock:
            self.found = toys
            self.labels = [{'id': key, 'name': name, 'type': kind}
                           for key, name, kind in found]
            self.last_error = None
            return list(self.labels)

    def connect(self, slot, key):
        if slot not in ('a', 'b'):
            raise ValueError('Invalid slot')
        with self.lock:
            if key not in self.found:
                raise ValueError('Robot not in most recent scan. Scan again.')
            if any(v['id'] == key for s, v in self.robots.items() if s != slot):
                raise ValueError('This robot is already assigned to the other slot.')
            self.disconnect(slot)
            label = next((v['name'] for v in self.labels if v['id'] == key), key)
            if self.demo:
                self.robots[slot] = {'name': label, 'id': key}
            else:
                if key.startswith('classic:'):
                    api = LegacySphero(self.found[key])
                    self.robots[slot] = {'name': label, 'id': key, 'ctx': None, 'api': api}
                else:
                    from spherov2.sphero_edu import SpheroEduAPI
                    ctx = SpheroEduAPI(self.found[key])
                    api = ctx.__enter__()
                    self.robots[slot] = {'name': label, 'id': key, 'ctx': ctx, 'api': api}
                try:
                    api.set_speed(0)
                except Exception:
                    self.disconnect(slot)
                    raise
            return {'connected': True, 'name': label}

    def disconnect(self, slot):
        with self.lock:
            obj = self.robots.pop(slot, None)
            self.last_drive.pop(slot, None)
            if obj and not self.demo:
                try:
                    obj['api'].set_speed(0)
                finally:
                    if obj['ctx'] is None:
                        obj['api'].close()
                    else:
                        obj['ctx'].__exit__(None, None, None)

    def _stop(self, slot):
        obj = self.robots.get(slot)
        self.last_drive.pop(slot, None)
        if obj and not self.demo:
            obj['api'].set_speed(0)

    def command(self, action, slots, targets=None, color=None):
        if not isinstance(slots, list) or not slots or any(s not in ('a', 'b') for s in slots):
            raise ValueError('Slots must be a nonempty list of a/b')
        if len(set(slots)) != len(slots):
            raise ValueError('Duplicate slot')
        if action not in ('drive', 'stop', 'color'):
            raise ValueError('Invalid action')
        if action == 'drive':
            if not isinstance(targets, dict) or set(targets) != set(slots):
                raise ValueError('Provide a drive target for each slot')
            validated = {}
            for slot in slots:
                target = targets[slot]
                if not isinstance(target, dict):
                    raise ValueError('Invalid target')
                heading, speed = target.get('heading'), target.get('speed')
                if type(heading) not in (int, float) or type(speed) not in (int, float):
                    raise ValueError('Heading and speed must be numbers')
                if not 0 <= heading < 360 or not 0 <= speed <= 100:
                    raise ValueError('Heading must be 0..359, speed 0..100')
                validated[slot] = (int(heading), int(round(speed * 2.55)))
        if action == 'color':
            if not isinstance(color, list) or len(color) != 3 or any(type(c) is not int or not 0 <= c <= 255 for c in color):
                raise ValueError('RGB channels must be 0..255')
        results = {}
        with self.lock:
            for slot in slots:
                obj = self.robots.get(slot)
                if not obj:
                    results[slot] = 'not connected'
                    continue
                try:
                    if action == 'stop':
                        self._stop(slot)
                    elif action == 'drive':
                        heading, speed = validated[slot]
                        if not self.demo:
                            obj['api'].set_heading(heading)
                            obj['api'].set_speed(speed)
                        if speed:
                            self.last_drive[slot] = self.clock()
                        else:
                            self.last_drive.pop(slot, None)
                    elif action == 'color' and not self.demo:
                        from spherov2.types import Color
                        obj['api'].set_main_led(Color(*color))
                    results[slot] = 'ok'
                except Exception as exc:
                    results[slot] = 'error: ' + str(exc)
                    self.last_error = f'{slot}: {exc}'
                    try:
                        self._stop(slot)
                    except Exception:
                        pass
            return results

    def watchdog(self):
        with self.lock:
            expired = [slot for slot, last in self.last_drive.items()
                       if self.clock() - last > DEADMAN_SECONDS]
            for slot in expired:
                try:
                    self._stop(slot)
                except Exception as exc:
                    self.last_error = f'Watchdog {slot}: {exc}'
            return expired

    def close(self):
        for slot in list(self.robots):
            try:
                self.disconnect(slot)
            except Exception:
                traceback.print_exc()


BRIDGE = Bridge(DEMO)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'static'), **kwargs)

    def reply(self, value, status=200):
        payload = json.dumps(value).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def authorize(self):
        if not hmac.compare_digest(self.headers.get('X-Sphero-Token', ''), TOKEN):
            self.reply({'error': 'Unauthorized. Reopen the link printed in Terminal.'}, 401)
            return False
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/api/status':
            if self.authorize():
                self.reply(BRIDGE.status())
            return
        if path.startswith('/api/'):
            return self.reply({'error': 'Unknown endpoint'}, 404)
        return super().do_GET()

    def do_POST(self):
        if not self.authorize():
            return
        path = urlsplit(self.path).path
        if path not in ('/api/scan', '/api/connect', '/api/disconnect', '/api/command'):
            return self.reply({'error': 'Unknown endpoint'}, 404)
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 0 or length > 4096:
                return self.reply({'error': 'Invalid request size'}, 413)
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict):
                raise ValueError('Body must be an object')
            if path == '/api/scan':
                result = BRIDGE.scan()
            elif path == '/api/connect':
                result = BRIDGE.connect(data.get('slot'), data.get('id'))
            elif path == '/api/disconnect':
                BRIDGE.disconnect(data.get('slot'))
                result = {'ok': True}
            else:
                result = BRIDGE.command(data.get('action'), data.get('slots'), data.get('targets'), data.get('color'))
            self.reply({'result': result})
        except (ValueError, KeyError, TypeError) as exc:
            self.reply({'error': str(exc)}, 400)
        except Exception as exc:
            traceback.print_exc()
            BRIDGE.last_error = str(exc)
            self.reply({'error': str(exc)}, 500)


def local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('192.0.2.1', 80))
            return sock.getsockname()[0]
    except OSError:
        return 'YOUR-MAC-IP'


def watchdog_loop():
    while True:
        time.sleep(0.15)
        BRIDGE.watchdog()


def main():
    threading.Thread(target=watchdog_loop, daemon=True).start()
    print(f'Sphero Laboratory ({"demo" if DEMO else "hardware"})', flush=True)
    print(f'On Mac: http://localhost:{PORT}/?token={TOKEN}', flush=True)
    print(f'On iPhone (same Wi-Fi): http://{local_ip()}:{PORT}/?token={TOKEN}', flush=True)
    print('The access link is private. Keep Terminal open; Ctrl+C to stop.', flush=True)
    try:
        ThreadingHTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        BRIDGE.close()


if __name__ == '__main__':
    main()
