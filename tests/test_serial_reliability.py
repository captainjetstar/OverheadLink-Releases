from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from queue import Queue

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from overheadlink.serial_manager import SerialConnection
from overheadlink.protocol import encode_message


class SerialReliabilityTests(unittest.TestCase):
    def connection(self):
        with patch("overheadlink.serial_manager.serial", object()):
            return SerialConnection("COM20", lambda *args: None)

    def test_write_bursts_yield_for_reads(self):
        connection = self.connection()
        class Port:
            def __init__(self): self.written = []
            def write(self, value): self.written.append(value)
        connection._serial = Port()
        for _ in range(10): connection._writes.put(b"test")
        connection._drain_writes()
        self.assertEqual(len(connection._serial.written), 4)
        self.assertEqual(connection._writes.qsize(), 6)

    def test_invalid_data_is_diagnosed_and_valid_heartbeat_recovers(self):
        connection = self.connection()
        connection._feed_rx(b"17,OK;\n")
        self.assertEqual(connection.invalid_messages, 1)
        self.assertIn("115200", connection.last_error)
        connection._feed_rx(encode_message("HEARTBEAT", 1000))
        self.assertEqual(connection.last_error, "")
