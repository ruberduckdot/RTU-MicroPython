# Modbus RTU 프레임 분리·주소 처리·부분 수신 시험 (가짜 UART, 가짜 시계 사용)
import struct
import unittest

import _path  # noqa: F401
import modbus as mb


class FakeUart:
    def __init__(self):
        self.rx = bytearray()
        self.tx = []

    def push(self, data):
        self.rx += data

    def any(self):
        return len(self.rx)

    def readinto(self, buf, n):
        n = min(n, len(self.rx))
        buf[:n] = self.rx[:n]
        del self.rx[:n]
        return n

    def write(self, data):
        self.tx.append(bytes(data))
        return len(data)


class Clock:
    def __init__(self):
        self.t = 0

    def __call__(self):
        return self.t


def frame(addr, pdu):
    return mb.rtu_build_frame(addr, pdu)


class RtuTest(unittest.TestCase):
    def setUp(self):
        self.uart = FakeUart()
        self.clock = Clock()
        self.dm = mb.DataMap()
        self.slave = mb.RtuSlave(self.uart, self.dm, 9600, clock=self.clock)

    def poll(self, advance_us=0):
        self.clock.t += advance_us
        self.slave.poll()

    def test_t35(self):
        self.assertEqual(mb.rtu_t35_us(9600), 4010)
        self.assertEqual(mb.rtu_t35_us(19200), 2005)
        self.assertEqual(mb.rtu_t35_us(115200), 1750)

    def test_read_request(self):
        self.uart.push(frame(255, struct.pack(">BHH", 3, 15, 1)))
        self.poll()
        self.assertEqual(self.uart.tx, [frame(255, bytes([3, 2, 0, 255]))])

    def test_other_address_ignored(self):
        self.uart.push(frame(1, struct.pack(">BHH", 3, 0, 1)))
        self.poll()
        self.assertEqual(self.uart.tx, [])
        self.assertEqual(self.slave.rx_frames, 1)

    def test_partial_frame(self):
        f = frame(255, struct.pack(">BHHBH", 0x10, 0, 1, 2, 300))
        self.uart.push(f[:4])
        self.poll()
        self.assertEqual(self.uart.tx, [])
        self.uart.push(f[4:])
        self.poll(1000)
        self.assertEqual(self.uart.tx, [frame(255, struct.pack(">BHH", 0x10, 0, 1))])
        self.assertEqual(self.dm.dac, 300)

    def test_back_to_back_frames(self):
        f1 = frame(255, struct.pack(">BHH", 5, 0, 0xFF00))
        f2 = frame(1, struct.pack(">BHH", 3, 0, 1))  # 다른 국 요청
        f3 = frame(255, struct.pack(">BHH", 1, 0, 13))
        self.uart.push(f1 + f2 + f3)
        self.poll()
        self.assertEqual(len(self.uart.tx), 2)
        self.assertEqual(self.uart.tx[0], f1)
        self.assertEqual(self.uart.tx[1], frame(255, bytes([1, 2, 1, 0])))

    def test_crc_error_dropped(self):
        f = bytearray(frame(255, struct.pack(">BHH", 3, 0, 1)))
        f[-1] ^= 0xFF
        self.uart.push(f)
        self.poll()
        self.assertEqual(self.uart.tx, [])
        self.assertEqual(self.slave.crc_errors, 1)
        # 이후 정상 프레임은 처리되어야 함
        self.uart.push(frame(255, struct.pack(">BHH", 3, 0, 1)))
        self.poll(10000)
        self.assertEqual(len(self.uart.tx), 1)

    def test_incomplete_frame_timeout(self):
        self.uart.push(frame(255, struct.pack(">BHH", 3, 0, 1))[:5])
        self.poll()
        self.poll(4000)  # 아직 무신호 기준(5 ms) 미만
        self.assertEqual(self.slave.dropped, 0)
        self.poll(2000)
        self.assertEqual(self.slave.dropped, 1)
        self.uart.push(frame(255, struct.pack(">BHH", 3, 0, 1)))
        self.poll()
        self.assertEqual(len(self.uart.tx), 1)

    def test_unknown_function_after_idle(self):
        self.uart.push(frame(255, bytes([0x2B, 0x0E, 0x01, 0x00])))
        self.poll()
        self.assertEqual(self.uart.tx, [])  # 길이 불명 → 무신호 구간 대기
        self.poll(6000)
        self.assertEqual(self.uart.tx, [frame(255, bytes([0xAB, 0x01]))])

    def test_exception_response(self):
        self.uart.push(frame(255, struct.pack(">BHH", 6, 0, 5000)))
        self.poll()
        self.assertEqual(self.uart.tx, [frame(255, bytes([0x86, 0x03]))])

    def test_broadcast_write_no_response(self):
        self.uart.push(frame(0, struct.pack(">BHH", 6, 0, 1000)))
        self.uart.push(frame(0, struct.pack(">BHH", 3, 0, 1)))
        self.poll()
        self.assertEqual(self.uart.tx, [])
        self.assertEqual(self.dm.dac, 1000)

    def test_unit_id_change(self):
        self.uart.push(frame(255, struct.pack(">BHH", 6, 15, 250)))
        self.poll()
        self.assertEqual(self.uart.tx[0], frame(255, struct.pack(">BHH", 6, 15, 250)))
        self.uart.push(frame(255, struct.pack(">BHH", 3, 15, 1)))
        self.uart.push(frame(250, struct.pack(">BHH", 3, 15, 1)))
        self.poll()
        self.assertEqual(self.uart.tx[1:], [frame(250, bytes([3, 2, 0, 250]))])

    def test_overflow_noise(self):
        self.uart.push(bytes([0x00, 0x2B]) + bytes(400))
        self.poll()
        self.assertGreaterEqual(self.slave.dropped, 1)
        self.uart.rx = bytearray()
        self.poll(10000)
        self.uart.push(frame(255, struct.pack(">BHH", 4, 0, 2)))
        self.poll()
        self.assertEqual(self.uart.tx, [frame(255, bytes([4, 4, 0, 0, 0, 0]))])


if __name__ == "__main__":
    unittest.main()
