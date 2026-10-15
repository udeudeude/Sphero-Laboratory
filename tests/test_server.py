"""Bridge behavior tests. No Bluetooth equipment or third-party libraries required."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Bridge, DEADMAN_SECONDS


class FakeAPI:
    def __init__(self):
        self.calls = []

    def set_heading(self, value):
        self.calls.append(('heading', value))

    def set_speed(self, value):
        self.calls.append(('speed', value))


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.bridge = Bridge(demo=True, clock=lambda: self.now)
        self.bridge.scan()
        self.bridge.connect('a', 'demo-2')
        self.bridge.connect('b', 'demo-sprk')

    def test_two_robots_and_unique_assignment(self):
        self.assertEqual(set(self.bridge.status()['robots']), {'a', 'b'})
        with self.assertRaisesRegex(ValueError, 'already assigned'):
            self.bridge.connect('a', 'demo-sprk')

    def test_discovered_id_not_index(self):
        with self.assertRaisesRegex(ValueError, 'most recent scan'):
            self.bridge.connect('a', '0')

    def test_drive_and_watchdog(self):
        self.assertEqual(self.bridge.command('drive', ['a', 'b'],
            {'a': {'heading': 0, 'speed': 20}, 'b': {'heading': 180, 'speed': 20}}),
            {'a': 'ok', 'b': 'ok'})
        self.now += DEADMAN_SECONDS + .01
        self.assertEqual(set(self.bridge.watchdog()), {'a', 'b'})
        self.assertEqual(self.bridge.last_drive, {})

    def test_malformed_drive_does_not_move(self):
        for data in (
            {'a': {'heading': 20, 'speed': 101}},
            {'a': {'heading': -1, 'speed': 5}},
            {'a': {'heading': 'north', 'speed': 5}},
            {'a': {'heading': 12, 'speed': 5}, 'b': {'heading': 7, 'speed': 5}},
        ):
            with self.assertRaises(ValueError):
                self.bridge.command('drive', ['a'], data)
        self.assertFalse(self.bridge.last_drive)

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.bridge.command('stop', ['z'])
        with self.assertRaises(ValueError):
            self.bridge.command('stop', ['a', 'a'])
        with self.assertRaises(ValueError):
            self.bridge.command('color', ['a'], color=[0, 256, 2])
        with self.assertRaises(ValueError):
            self.bridge.command('color', ['a'], color=['0', 1, 1])

    def test_hardware_api_continuous_speed(self):
        api = FakeAPI()
        self.bridge.demo = False
        self.bridge.robots['a'] = {'name': 'Fake', 'id': 'fake', 'api': api}
        self.assertEqual(self.bridge.command('drive', ['a'],
             {'a': {'heading': 90, 'speed': 25}}), {'a': 'ok'})
        self.assertEqual(api.calls, [('heading', 90), ('speed', 64)])
        self.now += 0.8
        self.bridge.watchdog()
        self.assertEqual(api.calls[-1], ('speed', 0))

    def test_stop_removes_watchdog(self):
        self.bridge.command('drive', ['a'], {'a': {'heading': 20, 'speed': 40}})
        self.assertEqual(self.bridge.command('stop', ['a', 'b']), {'a': 'ok', 'b': 'ok'})
        self.assertEqual(self.bridge.last_drive, {})


if __name__ == '__main__':
    unittest.main()
