# Modbus TCP: MBAP 분리·검증 단위 시험과 루프백 왕복 시험(tools/mb_tcp_check.py 사용)
import struct
import threading
import time
import unittest

import _path  # noqa: F401
import mb_tcp_check
import modbus as mb


def adu(tid, uid, pdu, pid=0, length=None):
    if length is None:
        length = len(pdu) + 1
    return struct.pack(">HHHB", tid, pid, length, uid) + pdu


class MbapReaderTest(unittest.TestCase):
    def test_single(self):
        r = mb.MbapReader()
        r.feed(adu(7, 255, b"\x03\x00\x00\x00\x01"))
        self.assertEqual(r.next_adu(), (7, 255, b"\x03\x00\x00\x00\x01"))
        self.assertIsNone(r.next_adu())
        self.assertEqual(r.pending(), 0)

    def test_byte_by_byte(self):
        r = mb.MbapReader()
        data = adu(1, 1, b"\x01\x00\x00\x00\x0d")
        for i, b in enumerate(data):
            r.feed(bytes([b]))
            got = r.next_adu()
            if i < len(data) - 1:
                self.assertIsNone(got)
        self.assertEqual(got, (1, 1, b"\x01\x00\x00\x00\x0d"))

    def test_pipelined(self):
        r = mb.MbapReader()
        r.feed(adu(1, 255, b"\x03\x00\x00\x00\x01") + adu(2, 255, b"\x04\x00\x00\x00\x02")[:9])
        self.assertEqual(r.next_adu()[0], 1)
        self.assertIsNone(r.next_adu())
        r.feed(adu(2, 255, b"\x04\x00\x00\x00\x02")[9:])
        self.assertEqual(r.next_adu()[0], 2)

    def test_bad_protocol_id(self):
        r = mb.MbapReader()
        r.feed(adu(1, 255, b"\x03\x00\x00\x00\x01", pid=1))
        with self.assertRaises(mb.MbapError):
            r.next_adu()

    def test_bad_length(self):
        for length in (0, 1, 255, 0xFFFF):
            r = mb.MbapReader()
            r.feed(adu(1, 255, b"\x03", length=length))
            with self.assertRaises(mb.MbapError):
                r.next_adu()

    def test_overflow(self):
        r = mb.MbapReader()
        with self.assertRaises(mb.MbapError):
            r.feed(bytes(600))

    def test_unit_id_policy(self):
        dm = mb.DataMap()
        pdu = b"\x03\x00\x0f\x00\x01"
        for uid in (255, 0):
            self.assertEqual(mb.tcp_process_adu(dm, 9, uid, pdu), adu(9, uid, b"\x03\x02\x00\xff"))
        self.assertEqual(mb.tcp_process_adu(dm, 9, 1, pdu), adu(9, 1, b"\x83\x0b"))


class LoopbackTest(unittest.TestCase):
    """CPython에서 TcpSlave를 띄우고 PC 도구로 전체 시험을 수행함."""

    def setUp(self):
        self.dm = mb.DataMap()
        self.dm.ir[0] = 1234
        self.dm.ir[1] = 567
        self.logs = []
        self.slave = mb.TcpSlave(self.dm, port=0, bind_ip="127.0.0.1", log=self.logs.append)
        self.slave.start()
        self._run = True
        self.th = threading.Thread(target=self._loop, daemon=True)
        self.th.start()

    def _loop(self):
        while self._run:
            self.slave.poll()
            time.sleep(0.001)

    def tearDown(self):
        self._run = False
        self.th.join(2)
        self.slave.stop()

    def test_full_check(self):
        out = []
        passed, failed = mb_tcp_check.run_checks("127.0.0.1", self.slave.port, 255, True, 2.0, out.append)
        self.assertEqual(failed, 0, "\n".join(out))
        self.assertEqual(passed, 29)  # 읽기 5 + 쓰기 6 + 예외 15 + 스트림 3
        # 시험 후 원래 값으로 복원되어야 함
        self.assertEqual(list(self.dm.coils), [0] * 13)
        self.assertEqual(self.dm.dac, 0)

    def test_bad_mbap_closes_connection(self):
        import socket

        s = socket.create_connection(("127.0.0.1", self.slave.port), timeout=2)
        s.sendall(adu(1, 255, b"\x03\x00\x00\x00\x01", pid=5))
        self.assertEqual(s.recv(16), b"")  # 서버가 연결을 닫음
        s.close()

    def test_client_limit(self):
        import socket

        socks = [socket.create_connection(("127.0.0.1", self.slave.port), timeout=2) for _ in range(3)]
        try:
            self.assertEqual(socks[2].recv(16), b"")  # 3번째 연결은 거부됨
            socks[0].sendall(adu(1, 255, b"\x03\x00\x0f\x00\x01"))
            self.assertEqual(socks[0].recv(64), adu(1, 255, b"\x03\x02\x00\xff"))
        finally:
            for s in socks:
                s.close()


if __name__ == "__main__":
    unittest.main()
