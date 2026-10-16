# CRC-16/MODBUS 및 RTU 프레임 생성·검사 시험
import unittest

import _path  # noqa: F401
import modbus


def crc_bitwise(data):
    """테이블 없이 비트 단위로 계산한 기준값."""
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


class CrcTest(unittest.TestCase):
    def test_check_value(self):
        # CRC-16/MODBUS 표준 검사값: "123456789" → 0x4B37
        self.assertEqual(modbus.crc16(b"123456789"), 0x4B37)

    def test_known_frame(self):
        # 01 03 00 00 00 01 요청의 CRC는 84 0A (하위 바이트 먼저)
        frame = modbus.rtu_build_frame(0x01, bytes([0x03, 0x00, 0x00, 0x00, 0x01]))
        self.assertEqual(frame.hex(), "010300000001840a")

    def test_table_matches_bitwise(self):
        for data in (b"", b"\x00", b"\xff" * 7, bytes(range(256))):
            self.assertEqual(modbus.crc16(data), crc_bitwise(data))

    def test_length_argument(self):
        self.assertEqual(modbus.crc16(b"123456789XX", 9), 0x4B37)

    def test_check_frame(self):
        f = bytearray(modbus.rtu_build_frame(0xFF, bytes([0x01, 0, 0, 0, 13])))
        self.assertTrue(modbus.rtu_check_frame(f))
        f[3] ^= 0x01
        self.assertFalse(modbus.rtu_check_frame(f))
        self.assertFalse(modbus.rtu_check_frame(b"\x01\x02\x03"))


if __name__ == "__main__":
    unittest.main()
