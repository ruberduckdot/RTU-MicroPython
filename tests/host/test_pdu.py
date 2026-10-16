# PDU 처리(데이터맵, 정상 응답, 예외 응답) 시험
import struct
import unittest

import _path  # noqa: F401
import modbus as mb


def req(fmt, *args):
    return struct.pack(">" + fmt, *args)


class PduTest(unittest.TestCase):
    def setUp(self):
        self.dm = mb.DataMap()

    def run_pdu(self, pdu):
        return mb.process_pdu(self.dm, pdu)

    def assertException(self, pdu, code):
        resp = self.run_pdu(pdu)
        self.assertEqual(resp, bytes([pdu[0] | 0x80, code]), "요청 %s" % pdu.hex())

    # --- 정상 동작 ---------------------------------------------------------
    def test_default_unit_id(self):
        self.assertEqual(self.dm.unit_id, 255)
        self.assertEqual(mb.DataMap(10).unit_id, 255)  # 범위 밖이면 기본값

    def test_read_coils_packing(self):
        self.dm.coils[0] = 1
        self.dm.coils[8] = 1
        self.dm.coils[12] = 1
        self.assertEqual(self.run_pdu(req("BHH", 1, 0, 13)), bytes([1, 2, 0x01, 0x11]))

    def test_read_discrete_inputs(self):
        self.dm.di[1] = 1
        self.assertEqual(self.run_pdu(req("BHH", 2, 0, 2)), bytes([2, 1, 0x02]))

    def test_read_holding_registers(self):
        self.dm.dac = 4095
        self.dm.coils[9] = 1
        resp = self.run_pdu(req("BHH", 3, 0, 16))
        self.assertEqual(resp[:2], bytes([3, 32]))
        regs = struct.unpack(">16H", resp[2:])
        self.assertEqual(regs[0], 4095)
        self.assertEqual(regs[1], 1 << 9)
        self.assertEqual(regs[2:15], (0,) * 13)
        self.assertEqual(regs[15], 255)

    def test_read_input_registers(self):
        self.dm.ir[0] = 0x1234
        self.dm.ir[1] = 0xFFFF
        self.assertEqual(self.run_pdu(req("BHH", 4, 0, 2)), bytes([4, 4, 0x12, 0x34, 0xFF, 0xFF]))

    def test_write_single_coil(self):
        pdu = req("BHH", 5, 12, 0xFF00)
        self.assertEqual(self.run_pdu(pdu), pdu)
        self.assertEqual(self.dm.coils[12], 1)
        self.assertTrue(self.dm.changed & mb.CHG_COILS)
        self.run_pdu(req("BHH", 5, 12, 0x0000))
        self.assertEqual(self.dm.coils[12], 0)

    def test_write_single_register(self):
        pdu = req("BHH", 6, 0, 4095)
        self.assertEqual(self.run_pdu(pdu), pdu)
        self.assertEqual(self.dm.dac, 4095)
        self.assertTrue(self.dm.changed & mb.CHG_DAC)

    def test_write_unit_id(self):
        self.run_pdu(req("BHH", 6, 15, 248))
        self.assertEqual(self.dm.unit_id, 248)
        self.assertTrue(self.dm.changed & mb.CHG_UNIT_ID)

    def test_write_multiple_coils(self):
        resp = self.run_pdu(req("BHHBBB", 0x0F, 0, 13, 2, 0xFF, 0x1F))
        self.assertEqual(resp, req("BHH", 0x0F, 0, 13))
        self.assertEqual(list(self.dm.coils), [1] * 13)
        self.assertEqual(self.dm.io_bits(), 0x1FFF)

    def test_write_multiple_registers(self):
        resp = self.run_pdu(req("BHHBH", 0x10, 0, 1, 2, 77))
        self.assertEqual(resp, req("BHH", 0x10, 0, 1))
        self.assertEqual(self.dm.dac, 77)

    # --- 예외 응답 ---------------------------------------------------------
    def test_illegal_function(self):
        for fc in (0x07, 0x08, 0x11, 0x16, 0x17, 0x2B, 0x7F):
            self.assertException(bytes([fc, 0, 0, 0, 1]), mb.EX_ILLEGAL_FUNCTION)

    def test_read_quantity_errors(self):
        self.assertException(req("BHH", 1, 0, 0), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 1, 0, 2001), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 3, 0, 0), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 3, 0, 126), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 4, 0, 126), mb.EX_ILLEGAL_DATA_VALUE)

    def test_read_address_errors(self):
        self.assertException(req("BHH", 1, 13, 1), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertException(req("BHH", 1, 12, 2), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertException(req("BHH", 2, 2, 1), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertException(req("BHH", 3, 16, 1), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertException(req("BHH", 3, 0xFFFF, 1), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertException(req("BHH", 4, 2, 1), mb.EX_ILLEGAL_DATA_ADDRESS)

    def test_short_or_long_pdu(self):
        self.assertException(bytes([0x03, 0x00]), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHHB", 0x03, 0, 1, 0), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(bytes([0x10, 0, 0]), mb.EX_ILLEGAL_DATA_VALUE)

    def test_write_single_coil_errors(self):
        self.assertException(req("BHH", 5, 0, 0x1234), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 5, 13, 0xFF00), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertEqual(self.dm.changed, 0)

    def test_write_single_register_errors(self):
        self.assertException(req("BHH", 6, 0, 4096), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 6, 1, 0), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertException(req("BHH", 6, 5, 0), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertException(req("BHH", 6, 15, 247), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 6, 15, 256), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHH", 6, 16, 0), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertEqual((self.dm.dac, self.dm.unit_id, self.dm.changed), (0, 255, 0))

    def test_write_multiple_coils_errors(self):
        self.assertException(req("BHHBB", 0x0F, 0, 9, 1, 0xFF), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHHB", 0x0F, 0, 0, 0), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHHBBB", 0x0F, 0, 8, 1, 0xFF, 0), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHHBB", 0x0F, 6, 8, 1, 0xFF), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertEqual(list(self.dm.coils), [0] * 13)

    def test_write_multiple_registers_atomic(self):
        # HR0 정상값 + HR1(읽기 전용) → 예외 02, HR0도 바뀌지 않아야 함
        self.assertException(req("BHHBHH", 0x10, 0, 2, 4, 100, 0), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertEqual(self.dm.dac, 0)
        # HR15 범위 밖 값
        self.assertException(req("BHHBH", 0x10, 15, 1, 2, 1), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHHBH", 0x10, 0, 1, 3, 1), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHHB", 0x10, 0, 124, 248), mb.EX_ILLEGAL_DATA_VALUE)
        self.assertException(req("BHHBH", 0x10, 16, 1, 2, 1), mb.EX_ILLEGAL_DATA_ADDRESS)
        self.assertEqual(self.dm.changed, 0)


if __name__ == "__main__":
    unittest.main()
