#!/usr/bin/env python3
"""RTU MCU Modbus TCP 왕복 시험 도구 (PC 측, CPython 표준 라이브러리만 사용).

사용 예:
    python3 tools/mb_tcp_check.py 192.168.0.100
    python3 tools/mb_tcp_check.py 192.168.0.100 --port 502 --unit 255
    python3 tools/mb_tcp_check.py 192.168.0.100 --no-write   # 출력 변경 없이 읽기·예외만 시험

시험 항목:
    - FC01·02·03·04 읽기, FC05·06·0F·10 쓰기 후 되읽기 확인
    - LED04~07(Coil 3~6)의 릴레이(Coil 9~12) 상태 연동, LED04~07 단독 쓰기 무시
    - 예외 코드 01(미지원 FC)·02(주소 범위)·03(값·수량·길이)
    - 한 번의 송신에 요청 2개(파이프라이닝), 요청을 둘로 나눈 부분 송신
쓰기 시험은 LED·릴레이·DAC 출력을 실제로 바꿈. 시험이 끝나면 시험 전
값으로 되돌림. 릴레이에 부하가 연결된 상태에서는 --no-write를 사용함.

종료 코드: 실패 항목 수(0이면 전부 통과).
"""

import argparse
import socket
import struct
import sys
import time

# 데이터맵(프로토콜 20260928, 0-based)
N_COILS = 13
N_DI = 2
N_HR = 16
N_IR = 2
HR_DAC = 0
HR_IO_BITS = 1
HR_UNIT_ID = 15
# LED04~07(Coil 3~6)은 Relay01~04(Coil 9~12) 상태를 따라감(쓰기 무시)
RELAY_LED_COILS = ((3, 9), (4, 10), (5, 11), (6, 12))


def mirror_relay_leds(coils):
    out = list(coils)
    for led, relay in RELAY_LED_COILS:
        out[led] = out[relay]
    return out


class ModbusException(Exception):
    def __init__(self, fc, code):
        Exception.__init__(self, "예외 응답 FC=0x%02X 코드=0x%02X" % (fc, code))
        self.fc = fc
        self.code = code


class MbTcpClient:
    def __init__(self, host, port=502, unit=255, timeout=2.0):
        self.unit = unit
        self._tid = 0
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)

    def close(self):
        self._sock.close()

    def _next_tid(self):
        self._tid = (self._tid + 1) & 0xFFFF
        return self._tid

    def build(self, pdu, unit=None, tid=None):
        if tid is None:
            tid = self._next_tid()
        if unit is None:
            unit = self.unit
        return tid, struct.pack(">HHHB", tid, 0, len(pdu) + 1, unit) + pdu

    def _recv_exact(self, n):
        out = b""
        while len(out) < n:
            chunk = self._sock.recv(n - len(out))
            if not chunk:
                raise ConnectionError("상대측이 연결을 닫음")
            out += chunk
        return out

    def recv_response(self, tid, unit=None):
        if unit is None:
            unit = self.unit
        hdr = self._recv_exact(7)
        rtid, pid, length, ruid = struct.unpack(">HHHB", hdr)
        if rtid != tid:
            raise ValueError("트랜잭션 ID 불일치: 요청 %d, 응답 %d" % (tid, rtid))
        if pid != 0:
            raise ValueError("프로토콜 ID 오류: %d" % pid)
        if ruid != unit:
            raise ValueError("Unit ID 불일치: 요청 %d, 응답 %d" % (unit, ruid))
        if length < 2 or length > 254:
            raise ValueError("MBAP 길이 오류: %d" % length)
        return self._recv_exact(length - 1)

    def raw_send(self, data):
        self._sock.sendall(data)

    def request(self, pdu, unit=None):
        tid, adu = self.build(pdu, unit)
        self._sock.sendall(adu)
        resp = self.recv_response(tid, unit)
        if resp[0] & 0x80:
            if resp[0] != (pdu[0] | 0x80) or len(resp) != 2:
                raise ValueError("예외 응답 형식 오류: %s" % resp.hex())
            raise ModbusException(pdu[0], resp[1])
        if resp[0] != pdu[0]:
            raise ValueError("응답 기능 코드 불일치: %s" % resp.hex())
        return resp

    # --- 기능 코드별 요청 -------------------------------------------------
    def _read_bits(self, fc, start, qty):
        resp = self.request(struct.pack(">BHH", fc, start, qty))
        nbytes = (qty + 7) // 8
        if resp[1] != nbytes or len(resp) != 2 + nbytes:
            raise ValueError("비트 응답 길이 오류: %s" % resp.hex())
        return [(resp[2 + i // 8] >> (i % 8)) & 1 for i in range(qty)]

    def _read_regs(self, fc, start, qty):
        resp = self.request(struct.pack(">BHH", fc, start, qty))
        if resp[1] != 2 * qty or len(resp) != 2 + 2 * qty:
            raise ValueError("레지스터 응답 길이 오류: %s" % resp.hex())
        return list(struct.unpack(">%dH" % qty, resp[2:]))

    def read_coils(self, start, qty):
        return self._read_bits(0x01, start, qty)

    def read_discrete_inputs(self, start, qty):
        return self._read_bits(0x02, start, qty)

    def read_holding_registers(self, start, qty):
        return self._read_regs(0x03, start, qty)

    def read_input_registers(self, start, qty):
        return self._read_regs(0x04, start, qty)

    def write_single_coil(self, addr, on):
        pdu = struct.pack(">BHH", 0x05, addr, 0xFF00 if on else 0x0000)
        if self.request(pdu) != pdu:
            raise ValueError("FC05 에코 응답 불일치")

    def write_single_register(self, addr, value):
        pdu = struct.pack(">BHH", 0x06, addr, value)
        if self.request(pdu) != pdu:
            raise ValueError("FC06 에코 응답 불일치")

    def write_multiple_coils(self, start, values):
        nbytes = (len(values) + 7) // 8
        packed = bytearray(nbytes)
        for i, v in enumerate(values):
            if v:
                packed[i // 8] |= 1 << (i % 8)
        pdu = struct.pack(">BHHB", 0x0F, start, len(values), nbytes) + bytes(packed)
        if self.request(pdu) != struct.pack(">BHH", 0x0F, start, len(values)):
            raise ValueError("FC0F 응답 불일치")

    def write_multiple_registers(self, start, values):
        pdu = struct.pack(">BHHB", 0x10, start, len(values), 2 * len(values))
        pdu += struct.pack(">%dH" % len(values), *values)
        if self.request(pdu) != struct.pack(">BHH", 0x10, start, len(values)):
            raise ValueError("FC10 응답 불일치")


class Runner:
    def __init__(self, log):
        self.log = log
        self.passed = 0
        self.failed = 0

    def check(self, name, fn):
        try:
            detail = fn()
        except Exception as e:  # 시험 항목별 실패를 모아서 보고함
            self.failed += 1
            self.log("[실패] %s: %s" % (name, e))
            return
        self.passed += 1
        self.log("[통과] %s%s" % (name, (" — %s" % detail) if detail else ""))

    def expect_exception(self, name, cli, pdu, code):
        def fn():
            try:
                resp = cli.request(pdu)
            except ModbusException as e:
                if e.code != code:
                    raise AssertionError("예외 코드 %02X 기대, %02X 수신" % (code, e.code))
                return "예외 0x%02X" % code
            raise AssertionError("예외 0x%02X 기대, 정상 응답 %s 수신" % (code, resp.hex()))

        self.check(name, fn)


def _eq(actual, expected, what):
    if actual != expected:
        raise AssertionError("%s 불일치: 기대 %r, 실제 %r" % (what, expected, actual))


def run_checks(host, port=502, unit=255, write=True, timeout=2.0, log=print):
    """전체 시험을 수행하고 (통과 수, 실패 수)를 반환함."""
    r = Runner(log)
    cli = MbTcpClient(host, port, unit, timeout)
    try:
        # --- 읽기 -----------------------------------------------------------
        state = {}

        def rd_coils():
            state["coils"] = cli.read_coils(0, N_COILS)
            return "Coil0~12=%s" % "".join(str(b) for b in state["coils"])

        def rd_di():
            v = cli.read_discrete_inputs(0, N_DI)
            return "SW1=%d SW2=%d (ON=1 여부는 앱 구현 기준)" % (v[0], v[1])

        def rd_hr():
            v = cli.read_holding_registers(0, N_HR)
            state["hr"] = v
            if not (248 <= v[HR_UNIT_ID] <= 255):
                raise AssertionError("HR15 Unit ID 범위 밖: %d" % v[HR_UNIT_ID])
            if v[HR_DAC] > 4095:
                raise AssertionError("HR0 DAC 범위 밖: %d" % v[HR_DAC])
            return "HR0=%d HR1=0x%04X HR15=%d" % (v[HR_DAC], v[HR_IO_BITS], v[HR_UNIT_ID])

        def rd_ir():
            v = cli.read_input_registers(0, N_IR)
            return "IR0=%d IR1=%d" % (v[0], v[1])

        def hr1_matches_coils():
            coils = cli.read_coils(0, N_COILS)
            bits = cli.read_holding_registers(HR_IO_BITS, 1)[0]
            _eq(bits, sum(b << i for i, b in enumerate(coils)), "HR1 비트필드")

        r.check("FC01 Coil 0~12 읽기", rd_coils)
        r.check("FC02 DI 0~1 읽기", rd_di)
        r.check("FC03 HR 0~15 읽기", rd_hr)
        r.check("FC04 IR 0~1 읽기", rd_ir)
        r.check("HR1 = Coil 비트필드 일치", hr1_matches_coils)

        # --- 쓰기·되읽기 -----------------------------------------------------
        if write and "coils" in state and "hr" in state:
            orig_coils = state["coils"]
            orig_dac = state["hr"][HR_DAC]

            def fc05():
                target = 0 if orig_coils[0] else 1
                cli.write_single_coil(0, target)
                _eq(cli.read_coils(0, 1)[0], target, "Coil0 되읽기")

            def fc0f():
                pattern = [(i + 1) % 2 for i in range(N_COILS)]
                cli.write_multiple_coils(0, pattern)
                _eq(cli.read_coils(0, N_COILS), mirror_relay_leds(pattern), "Coil 되읽기")
                hr1_matches_coils()

            def relay_led_follow():
                # 릴레이 1·3 ON, 2·4 OFF → LED04·06 ON, LED05·07 OFF
                for k, on in enumerate((1, 0, 1, 0)):
                    cli.write_single_coil(9 + k, on)
                _eq(cli.read_coils(3, 4), [1, 0, 1, 0], "LED04~07")
                for k in range(4):
                    cli.write_single_coil(9 + k, 0)
                _eq(cli.read_coils(3, 4), [0, 0, 0, 0], "LED04~07")

            def led_write_ignored():
                cli.write_single_coil(3, 1)  # 정상 응답이어야 함
                _eq(cli.read_coils(3, 1)[0], 0, "LED04(릴레이 OFF 상태 유지)")

            def fc06():
                cli.write_single_register(HR_DAC, 1234)
                _eq(cli.read_holding_registers(HR_DAC, 1)[0], 1234, "HR0 되읽기")

            def fc10():
                cli.write_multiple_registers(HR_DAC, [2048])
                _eq(cli.read_holding_registers(HR_DAC, 1)[0], 2048, "HR0 되읽기")

            def fc10_atomic():
                # HR0~1 동시 쓰기: HR1은 읽기 전용 → 예외 02, HR0은 바뀌면 안 됨
                try:
                    cli.write_multiple_registers(HR_DAC, [100, 0])
                except ModbusException as e:
                    _eq(e.code, 0x02, "예외 코드")
                else:
                    raise AssertionError("예외 02 기대, 정상 응답 수신")
                _eq(cli.read_holding_registers(HR_DAC, 1)[0], 2048, "부분 반영 없음(HR0)")

            def restore():
                cli.write_multiple_coils(0, orig_coils)
                cli.write_single_register(HR_DAC, orig_dac)
                _eq(cli.read_coils(0, N_COILS), orig_coils, "Coil 복원")
                _eq(cli.read_holding_registers(HR_DAC, 1)[0], orig_dac, "HR0 복원")

            r.check("FC05 Coil0 쓰기·되읽기", fc05)
            r.check("FC0F Coil 0~12 쓰기·되읽기", fc0f)
            r.check("릴레이 → LED04~07 연동", relay_led_follow)
            r.check("LED04 단독 쓰기 무시(정상 응답)", led_write_ignored)
            r.check("FC06 HR0=1234 쓰기·되읽기", fc06)
            r.check("FC10 HR0=2048 쓰기·되읽기", fc10)
            r.check("FC10 일부 주소 오류 시 전체 미반영", fc10_atomic)
            r.check("시험 전 값으로 복원", restore)
        elif write:
            log("[건너뜀] 읽기 실패로 쓰기 시험을 생략함")

        # --- 예외 응답 -------------------------------------------------------
        ex = r.expect_exception
        ex("미지원 FC 0x07 → 01", cli, bytes([0x07]), 0x01)
        ex("미지원 FC 0x17 → 01", cli, struct.pack(">BHHHHB", 0x17, 0, 1, 0, 1, 0), 0x01)
        ex("FC01 수량 0 → 03", cli, struct.pack(">BHH", 0x01, 0, 0), 0x03)
        ex("FC01 주소 13 → 02", cli, struct.pack(">BHH", 0x01, N_COILS, 1), 0x02)
        ex("FC02 주소 0, 수량 3 → 02", cli, struct.pack(">BHH", 0x02, 0, 3), 0x02)
        ex("FC03 수량 126 → 03", cli, struct.pack(">BHH", 0x03, 0, 126), 0x03)
        ex("FC03 주소 16 → 02", cli, struct.pack(">BHH", 0x03, N_HR, 1), 0x02)
        ex("FC04 주소 2 → 02", cli, struct.pack(">BHH", 0x04, N_IR, 1), 0x02)
        ex("FC05 값 0x1234 → 03", cli, struct.pack(">BHH", 0x05, 0, 0x1234), 0x03)
        ex("FC05 주소 13 → 02", cli, struct.pack(">BHH", 0x05, N_COILS, 0xFF00), 0x02)
        ex("FC06 HR0=4096 → 03", cli, struct.pack(">BHH", 0x06, HR_DAC, 4096), 0x03)
        ex("FC06 HR1 쓰기 → 02", cli, struct.pack(">BHH", 0x06, HR_IO_BITS, 0), 0x02)
        ex("FC06 HR15=1 → 03", cli, struct.pack(">BHH", 0x06, HR_UNIT_ID, 1), 0x03)
        ex("FC0F 바이트 수 불일치 → 03", cli, struct.pack(">BHHBB", 0x0F, 0, 9, 1, 0xFF), 0x03)
        ex("FC10 바이트 수 불일치 → 03", cli, struct.pack(">BHHBH", 0x10, 0, 1, 3, 0), 0x03)

        # --- 스트림 처리 -----------------------------------------------------
        def pipelined():
            t1, a1 = cli.build(struct.pack(">BHH", 0x03, HR_UNIT_ID, 1))
            t2, a2 = cli.build(struct.pack(">BHH", 0x01, 0, N_COILS))
            cli.raw_send(a1 + a2)
            p1 = cli.recv_response(t1)
            p2 = cli.recv_response(t2)
            _eq(p1[0], 0x03, "첫 응답 FC")
            _eq(p2[0], 0x01, "둘째 응답 FC")
            return "TID %d, %d 순서대로 수신" % (t1, t2)

        def fragmented():
            tid, adu = cli.build(struct.pack(">BHH", 0x04, 0, N_IR))
            cli.raw_send(adu[:5])
            time.sleep(0.2)
            cli.raw_send(adu[5:])
            p = cli.recv_response(tid)
            _eq(p[0], 0x04, "응답 FC")

        def unit_ff():
            tid, adu = cli.build(struct.pack(">BHH", 0x03, HR_UNIT_ID, 1), unit=0xFF)
            cli.raw_send(adu)
            p = cli.recv_response(tid, unit=0xFF)
            _eq(p[0], 0x03, "응답 FC")

        r.check("요청 2개 연속 송신(파이프라이닝)", pipelined)
        r.check("요청 분할 송신(부분 수신)", fragmented)
        r.check("Unit ID 0xFF 요청 응답", unit_ff)
    finally:
        cli.close()

    log("결과: 통과 %d, 실패 %d" % (r.passed, r.failed))
    return r.passed, r.failed


def main(argv=None):
    ap = argparse.ArgumentParser(description="RTU MCU Modbus TCP 왕복 시험")
    ap.add_argument("host", help="보드 IP 주소")
    ap.add_argument("--port", type=int, default=502)
    ap.add_argument("--unit", type=int, default=255, help="Unit ID(기본 255)")
    ap.add_argument("--timeout", type=float, default=2.0, help="응답 대기 시간(초)")
    ap.add_argument("--no-write", action="store_true", help="쓰기 시험 생략")
    args = ap.parse_args(argv)
    try:
        _, failed = run_checks(args.host, args.port, args.unit, not args.no_write, args.timeout)
    except OSError as e:
        print("연결 실패: %s" % e)
        return 255
    return min(failed, 254)


if __name__ == "__main__":
    sys.exit(main())
