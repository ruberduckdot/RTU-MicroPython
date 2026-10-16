# Modbus RTU/TCP 슬레이브 프로토콜 처리부
#
# 대상: IOTPLUS RTU MCU R1.0a (STM32F429, MicroPython stm32 포트)
# 데이터맵: 프로토콜 20260928, 0-based 주소
#   Coil 0~8 = LED01~09, Coil 9~12 = Relay01~04
#   DI   0~1 = SW1, SW2
#   HR0  = DAC 설정값(0~4095, R/W)
#   HR1  = LED·Relay 비트필드(R)
#   HR15 = Unit ID(248~255, 기본 255)
#   IR0  = 전압, IR1 = 전류
# 지원 FC: 01, 02, 03, 04, 05, 06, 0F, 10
#
# 이 모듈은 하드웨어에 직접 접근하지 않음. 앱(슈퍼루프)이 DataMap 값을
# 실제 핀·ADC·DAC와 동기화함. CPython에서도 동작하므로 호스트 단위 시험에
# 그대로 사용함.
#
# 업체 샘플(pycom-modbus 파생, GPL-3.0-or-later)의 코드는 복사하지 않고
# Modbus Application Protocol V1.1b3 / Modbus over Serial Line V1.02 기준으로
# 새로 작성함.

import struct

try:
    from time import ticks_ms, ticks_us, ticks_diff
except ImportError:  # CPython 호스트 시험 환경
    import time as _time

    def ticks_ms():
        return int(_time.monotonic() * 1000)

    def ticks_us():
        return int(_time.monotonic() * 1000000)

    def ticks_diff(a, b):
        return a - b

try:
    import errno as _errno
except ImportError:
    import uerrno as _errno

# ---------------------------------------------------------------------------
# 기능 코드 / 예외 코드
# ---------------------------------------------------------------------------
FC_READ_COILS = 0x01
FC_READ_DISCRETE_INPUTS = 0x02
FC_READ_HOLDING_REGISTERS = 0x03
FC_READ_INPUT_REGISTERS = 0x04
FC_WRITE_SINGLE_COIL = 0x05
FC_WRITE_SINGLE_REGISTER = 0x06
FC_WRITE_MULTIPLE_COILS = 0x0F
FC_WRITE_MULTIPLE_REGISTERS = 0x10

EX_ILLEGAL_FUNCTION = 0x01
EX_ILLEGAL_DATA_ADDRESS = 0x02
EX_ILLEGAL_DATA_VALUE = 0x03
EX_SERVER_DEVICE_FAILURE = 0x04
EX_GATEWAY_TARGET_FAILED = 0x0B

# ---------------------------------------------------------------------------
# 데이터맵 크기 (프로토콜 20260928)
# ---------------------------------------------------------------------------
N_COILS = 13
N_DISCRETE_INPUTS = 2
N_HOLDING_REGISTERS = 16
N_INPUT_REGISTERS = 2

HR_DAC = 0
HR_IO_BITS = 1
HR_UNIT_ID = 15

DAC_MAX = 4095
UNIT_ID_MIN = 248
UNIT_ID_MAX = 255
UNIT_ID_DEFAULT = 255

# DataMap.changed 비트: 원격 쓰기로 바뀐 항목을 앱에 알림
CHG_COILS = 0x01
CHG_DAC = 0x02
CHG_UNIT_ID = 0x04

# ---------------------------------------------------------------------------
# CRC-16/MODBUS (다항식 0xA001 반사형, 초기값 0xFFFF)
# ---------------------------------------------------------------------------


def _make_crc_table():
    table = []
    for i in range(256):
        c = i
        for _ in range(8):
            if c & 1:
                c = (c >> 1) ^ 0xA001
            else:
                c >>= 1
        table.append(c)
    return tuple(table)


_CRC_TABLE = _make_crc_table()


def crc16(data, length=None):
    """data[0:length]의 CRC-16/MODBUS 값을 반환함. 프레임에는 하위 바이트부터 실림."""
    if length is None:
        length = len(data)
    crc = 0xFFFF
    tbl = _CRC_TABLE
    for i in range(length):
        crc = (crc >> 8) ^ tbl[(crc ^ data[i]) & 0xFF]
    return crc


# ---------------------------------------------------------------------------
# 데이터맵
# ---------------------------------------------------------------------------


class DataMap:
    """슬레이브가 노출하는 Modbus 데이터 영역.

    coils/di는 0·1 값의 bytearray, ir은 0~65535 정수 리스트임.
    원격 쓰기가 일어나면 changed 비트를 세움. 앱은 값을 출력에 반영한 뒤
    changed를 0으로 지움.
    """

    def __init__(self, unit_id=UNIT_ID_DEFAULT):
        if not (UNIT_ID_MIN <= unit_id <= UNIT_ID_MAX):
            unit_id = UNIT_ID_DEFAULT
        self.coils = bytearray(N_COILS)
        self.di = bytearray(N_DISCRETE_INPUTS)
        self.ir = [0] * N_INPUT_REGISTERS
        self.dac = 0
        self.unit_id = unit_id
        self.changed = 0

    def io_bits(self):
        """HR1 값: 비트 n = Coil n (bit0~8 LED01~09, bit9~12 Relay01~04)."""
        v = 0
        c = self.coils
        for i in range(N_COILS):
            if c[i]:
                v |= 1 << i
        return v

    def hr_read(self, addr):
        if addr == HR_DAC:
            return self.dac
        if addr == HR_IO_BITS:
            return self.io_bits()
        if addr == HR_UNIT_ID:
            return self.unit_id
        return 0  # HR2~14 예약 영역은 0으로 읽힘

    def hr_check(self, addr, value):
        """쓰기 가능 여부 검사. 0이면 허용, 아니면 예외 코드."""
        if addr == HR_DAC:
            return 0 if value <= DAC_MAX else EX_ILLEGAL_DATA_VALUE
        if addr == HR_UNIT_ID:
            if UNIT_ID_MIN <= value <= UNIT_ID_MAX:
                return 0
            return EX_ILLEGAL_DATA_VALUE
        # HR1(읽기 전용)과 예약 영역은 쓰기 불가
        return EX_ILLEGAL_DATA_ADDRESS

    def hr_apply(self, addr, value):
        """hr_check 통과 후 호출함."""
        if addr == HR_DAC:
            self.dac = value
            self.changed |= CHG_DAC
        elif addr == HR_UNIT_ID:
            if value != self.unit_id:
                self.unit_id = value
                self.changed |= CHG_UNIT_ID


# ---------------------------------------------------------------------------
# PDU 처리
# ---------------------------------------------------------------------------


def exception_pdu(fc, code):
    return bytes(((fc | 0x80) & 0xFF, code))


def _pack_bits(src, start, qty):
    out = bytearray(2 + (qty + 7) // 8)
    out[1] = (qty + 7) // 8
    for i in range(qty):
        if src[start + i]:
            out[2 + (i >> 3)] |= 1 << (i & 7)
    return out


def _read_bits(fc, pdu, src, size):
    if len(pdu) != 5:
        return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
    start, qty = struct.unpack(">HH", pdu[1:5])
    if not (1 <= qty <= 2000):
        return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
    if start + qty > size:
        return exception_pdu(fc, EX_ILLEGAL_DATA_ADDRESS)
    out = _pack_bits(src, start, qty)
    out[0] = fc
    return bytes(out)


def _read_regs(fc, pdu, size, getter):
    if len(pdu) != 5:
        return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
    start, qty = struct.unpack(">HH", pdu[1:5])
    if not (1 <= qty <= 125):
        return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
    if start + qty > size:
        return exception_pdu(fc, EX_ILLEGAL_DATA_ADDRESS)
    out = bytearray(2 + 2 * qty)
    out[0] = fc
    out[1] = 2 * qty
    for i in range(qty):
        struct.pack_into(">H", out, 2 + 2 * i, getter(start + i) & 0xFFFF)
    return bytes(out)


def process_pdu(dm, pdu):
    """요청 PDU(기능 코드부터)를 처리하고 응답 PDU를 반환함.

    검사 순서는 Modbus 규격(기능 코드 → 수량·길이 → 주소 → 값)을 따름.
    쓰기 요청은 모든 값을 검사한 뒤에만 반영함(부분 반영 없음).
    """
    if len(pdu) < 1:
        return None
    fc = pdu[0]

    if fc == FC_READ_COILS:
        return _read_bits(fc, pdu, dm.coils, N_COILS)

    if fc == FC_READ_DISCRETE_INPUTS:
        return _read_bits(fc, pdu, dm.di, N_DISCRETE_INPUTS)

    if fc == FC_READ_HOLDING_REGISTERS:
        return _read_regs(fc, pdu, N_HOLDING_REGISTERS, dm.hr_read)

    if fc == FC_READ_INPUT_REGISTERS:
        ir = dm.ir
        return _read_regs(fc, pdu, N_INPUT_REGISTERS, lambda a: ir[a])

    if fc == FC_WRITE_SINGLE_COIL:
        if len(pdu) != 5:
            return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
        addr, value = struct.unpack(">HH", pdu[1:5])
        if value not in (0x0000, 0xFF00):
            return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
        if addr >= N_COILS:
            return exception_pdu(fc, EX_ILLEGAL_DATA_ADDRESS)
        dm.coils[addr] = 1 if value else 0
        dm.changed |= CHG_COILS
        return bytes(pdu)

    if fc == FC_WRITE_SINGLE_REGISTER:
        if len(pdu) != 5:
            return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
        addr, value = struct.unpack(">HH", pdu[1:5])
        if addr >= N_HOLDING_REGISTERS:
            return exception_pdu(fc, EX_ILLEGAL_DATA_ADDRESS)
        ex = dm.hr_check(addr, value)
        if ex:
            return exception_pdu(fc, ex)
        dm.hr_apply(addr, value)
        return bytes(pdu)

    if fc == FC_WRITE_MULTIPLE_COILS:
        if len(pdu) < 6:
            return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
        start, qty, nbytes = struct.unpack(">HHB", pdu[1:6])
        if not (1 <= qty <= 1968) or nbytes != (qty + 7) // 8 or len(pdu) != 6 + nbytes:
            return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
        if start + qty > N_COILS:
            return exception_pdu(fc, EX_ILLEGAL_DATA_ADDRESS)
        for i in range(qty):
            dm.coils[start + i] = (pdu[6 + (i >> 3)] >> (i & 7)) & 1
        dm.changed |= CHG_COILS
        return struct.pack(">BHH", fc, start, qty)

    if fc == FC_WRITE_MULTIPLE_REGISTERS:
        if len(pdu) < 6:
            return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
        start, qty, nbytes = struct.unpack(">HHB", pdu[1:6])
        if not (1 <= qty <= 123) or nbytes != 2 * qty or len(pdu) != 6 + nbytes:
            return exception_pdu(fc, EX_ILLEGAL_DATA_VALUE)
        if start + qty > N_HOLDING_REGISTERS:
            return exception_pdu(fc, EX_ILLEGAL_DATA_ADDRESS)
        for i in range(qty):
            value = (pdu[6 + 2 * i] << 8) | pdu[7 + 2 * i]
            ex = dm.hr_check(start + i, value)
            if ex:
                return exception_pdu(fc, ex)
        for i in range(qty):
            dm.hr_apply(start + i, (pdu[6 + 2 * i] << 8) | pdu[7 + 2 * i])
        return struct.pack(">BHH", fc, start, qty)

    return exception_pdu(fc, EX_ILLEGAL_FUNCTION)


_WRITE_FCS = (
    FC_WRITE_SINGLE_COIL,
    FC_WRITE_SINGLE_REGISTER,
    FC_WRITE_MULTIPLE_COILS,
    FC_WRITE_MULTIPLE_REGISTERS,
)

# ---------------------------------------------------------------------------
# Modbus RTU 프레임 처리
# ---------------------------------------------------------------------------

RTU_MAX_ADU = 256


def rtu_request_length(buf, n):
    """요청 프레임의 전체 길이(주소·CRC 포함)를 반환함.

    0  : 길이를 판단하기에 바이트가 부족함
    -1 : 지원하지 않는 기능 코드라 길이를 알 수 없음(무신호 구간으로 판단)
    """
    if n < 2:
        return 0
    fc = buf[1]
    if 1 <= fc <= 6:
        return 8
    if fc == FC_WRITE_MULTIPLE_COILS or fc == FC_WRITE_MULTIPLE_REGISTERS:
        if n < 7:
            return 0
        return 9 + buf[6]
    return -1


def rtu_check_frame(frame, length=None):
    """CRC가 맞으면 True. 최소 길이 4바이트(주소+FC+CRC)."""
    if length is None:
        length = len(frame)
    if length < 4:
        return False
    crc = crc16(frame, length - 2)
    return frame[length - 2] == (crc & 0xFF) and frame[length - 1] == (crc >> 8)


def rtu_build_frame(addr, pdu):
    frame = bytearray(len(pdu) + 3)
    frame[0] = addr
    frame[1:1 + len(pdu)] = pdu
    crc = crc16(frame, len(pdu) + 1)
    frame[-2] = crc & 0xFF
    frame[-1] = crc >> 8
    return bytes(frame)


def rtu_t35_us(baudrate):
    """3.5 문자 시간(us). 1문자 = 11비트, 19200 bps 초과 시 1750 us 고정."""
    if baudrate > 19200:
        return 1750
    return (35 * 11 * 1000000) // (10 * baudrate)


class RtuSlave:
    """UART 기반 Modbus RTU 슬레이브(비차단).

    uart: any(), readinto(buf, n), write(buf)를 제공하는 객체(machine.UART)
    프레임 구분은 기능 코드별 길이 + CRC 검사를 우선함. 길이를 알 수 없거나
    미완성 프레임은 무신호 시간(idle_us)이 지나면 정리함. 슈퍼루프 주기가
    3.5 문자 시간보다 길어도 도착 바이트를 잃지 않도록 하기 위함임.
    """

    def __init__(self, uart, dm, baudrate, idle_us=None, clock=None):
        self._uart = uart
        self._dm = dm
        self._buf = bytearray(RTU_MAX_ADU)
        self._mv = memoryview(self._buf)
        self._n = 0
        self._clock = clock or ticks_us
        self._t_last = self._clock()
        if idle_us is None:
            idle_us = max(rtu_t35_us(baudrate), 5000)
        self._idle_us = idle_us
        # 진단 카운터
        self.rx_frames = 0
        self.crc_errors = 0
        self.dropped = 0

    def _consume(self, k):
        n = self._n
        if k >= n:
            self._n = 0
        else:
            self._buf[0:n - k] = self._buf[k:n]
            self._n = n - k

    def _handle(self, length):
        buf = self._buf
        if not rtu_check_frame(buf, length):
            # CRC 오류: 재동기화를 위해 버퍼 전체를 버림(마스터 재시도에 맡김)
            self.crc_errors += 1
            self._n = 0
            return
        self.rx_frames += 1
        addr = buf[0]
        dm = self._dm
        if addr != dm.unit_id and addr != 0:
            self._consume(length)
            return
        pdu = bytes(buf[1:length - 2])
        self._consume(length)
        if addr == 0:
            # 브로드캐스트: 쓰기만 실행하고 응답하지 않음
            if pdu[0] in _WRITE_FCS:
                process_pdu(dm, pdu)
            return
        resp = process_pdu(dm, pdu)
        if resp:
            self._uart.write(rtu_build_frame(addr, resp))

    def poll(self):
        """수신 바이트를 읽고 완결 프레임을 처리함. 블로킹하지 않음."""
        now = self._clock()
        k = self._uart.any()
        if k:
            space = RTU_MAX_ADU - self._n
            if k > space:
                k = space
            if k > 0:
                got = self._uart.readinto(self._mv[self._n:self._n + k], k)
                if got:
                    self._n += got
            self._t_last = now
            if self._n >= RTU_MAX_ADU:
                # 최대 ADU를 넘는 연속 수신은 잡음으로 보고 버림
                self.dropped += 1
                self._n = 0
                return
        idle = ticks_diff(now, self._t_last) >= self._idle_us
        while self._n:
            length = rtu_request_length(self._buf, self._n)
            if length > 0:
                if length > RTU_MAX_ADU:
                    self.dropped += 1
                    self._n = 0
                elif self._n >= length:
                    self._handle(length)
                    continue
                elif idle:
                    self.dropped += 1
                    self._n = 0
                break
            if length < 0 and idle:
                # 길이를 모르는 기능 코드: 무신호 구간까지를 한 프레임으로 처리
                self._handle(self._n)
                continue
            if length == 0 and idle:
                self.dropped += 1
                self._n = 0
            break


# ---------------------------------------------------------------------------
# Modbus TCP(MBAP) 처리
# ---------------------------------------------------------------------------

MBAP_LEN = 7
TCP_MAX_ADU = 260


class MbapError(ValueError):
    pass


class MbapReader:
    """TCP 스트림에서 MBAP 단위로 요청을 분리함.

    한 번의 recv에 여러 요청이 붙어 오거나(파이프라이닝) 요청이 쪼개져 와도
    처리함. 헤더가 규격을 벗어나면 MbapError를 발생시키며, 호출 측은 해당
    연결을 닫아야 함(스트림 재동기화 수단이 없음).
    """

    def __init__(self):
        self._buf = bytearray(TCP_MAX_ADU * 2)
        self._n = 0

    def pending(self):
        return self._n

    def feed(self, data):
        n = self._n
        k = len(data)
        if n + k > len(self._buf):
            raise MbapError("수신 버퍼 초과")
        self._buf[n:n + k] = data
        self._n = n + k

    def next_adu(self):
        """완결된 요청이 있으면 (tid, unit_id, pdu)를, 없으면 None을 반환함."""
        n = self._n
        if n < MBAP_LEN:
            return None
        buf = self._buf
        tid, pid, length, uid = struct.unpack(">HHHB", buf[0:MBAP_LEN])
        if pid != 0:
            raise MbapError("프로토콜 ID 오류")
        if length < 2 or length > TCP_MAX_ADU - 6:
            raise MbapError("MBAP 길이 오류")
        total = 6 + length
        if n < total:
            return None
        pdu = bytes(buf[MBAP_LEN:total])
        if total < n:
            buf[0:n - total] = buf[total:n]
        self._n = n - total
        return tid, uid, pdu


def tcp_build_adu(tid, uid, pdu):
    return struct.pack(">HHHB", tid, 0, len(pdu) + 1, uid) + pdu


def tcp_unit_accepted(dm, uid):
    """TCP에서 응답할 Unit ID: 자국 ID, 0xFF(TCP 관례), 0."""
    return uid == dm.unit_id or uid == 0xFF or uid == 0


def tcp_process_adu(dm, tid, uid, pdu):
    if not tcp_unit_accepted(dm, uid):
        return tcp_build_adu(tid, uid, exception_pdu(pdu[0], EX_GATEWAY_TARGET_FAILED))
    resp = process_pdu(dm, pdu)
    if resp is None:
        return None
    return tcp_build_adu(tid, uid, resp)


def _would_block(e):
    code = e.args[0] if e.args else None
    return code in (_errno.EAGAIN, getattr(_errno, "EWOULDBLOCK", _errno.EAGAIN), _errno.ETIMEDOUT)


class _Client:
    def __init__(self, sock, now):
        self.sock = sock
        self.reader = MbapReader()
        self.t_last = now


class TcpSlave:
    """비차단 Modbus TCP 슬레이브.

    start() 후 슈퍼루프에서 poll()을 반복 호출함. 동시 연결 수를 제한하고,
    idle_ms 동안 요청이 없는 연결은 닫음(케이블 분리 등 반개방 연결 정리).
    """

    def __init__(self, dm, port=502, max_clients=2, idle_ms=60000, bind_ip="0.0.0.0", log=print):
        self._dm = dm
        self.port = port
        self._bind_ip = bind_ip
        self._max = max_clients
        self._idle_ms = idle_ms
        self._log = log
        self._lsock = None
        self._clients = []

    def start(self):
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # 튜플 직접 전달은 포트마다 지원이 달라 getaddrinfo 결과를 사용함
        s.bind(socket.getaddrinfo(self._bind_ip, self.port)[0][-1])
        s.listen(self._max)
        s.setblocking(False)
        self._lsock = s
        if self.port == 0 and hasattr(s, "getsockname"):
            self.port = s.getsockname()[1]
        self._log("Modbus TCP 대기 시작: 포트 %d" % self.port)

    def stop(self):
        for c in self._clients:
            c.sock.close()
        self._clients = []
        if self._lsock:
            self._lsock.close()
            self._lsock = None

    def client_count(self):
        return len(self._clients)

    def _close(self, c, why):
        try:
            c.sock.close()
        except OSError:
            pass
        if c in self._clients:
            self._clients.remove(c)
        self._log("Modbus TCP 연결 종료: %s" % why)

    def _accept(self, now):
        try:
            sock, addr = self._lsock.accept()
        except OSError as e:
            if _would_block(e):
                return
            raise
        if len(self._clients) >= self._max:
            sock.close()
            self._log("Modbus TCP 연결 거부: 최대 연결 수 초과")
            return
        sock.setblocking(False)
        self._clients.append(_Client(sock, now))
        self._log("Modbus TCP 연결 수락: %s" % (addr,))

    def _service(self, c, now):
        try:
            data = c.sock.recv(TCP_MAX_ADU)
        except OSError as e:
            if _would_block(e):
                if ticks_diff(now, c.t_last) > self._idle_ms:
                    self._close(c, "유휴 시간 초과")
                return
            self._close(c, "수신 오류 %s" % (e.args[0] if e.args else e))
            return
        if not data:
            self._close(c, "상대측 종료")
            return
        c.t_last = now
        try:
            c.reader.feed(data)
            while True:
                req = c.reader.next_adu()
                if req is None:
                    break
                resp = tcp_process_adu(self._dm, req[0], req[1], req[2])
                if resp is None:
                    continue
                sent = c.sock.send(resp)
                if sent is not None and sent != len(resp):
                    # 송신 버퍼 부족: 응답이 잘리면 스트림이 깨지므로 연결을 닫음
                    self._close(c, "송신 불완전")
                    return
        except MbapError as e:
            self._close(c, "MBAP 오류 %s" % e)
        except OSError as e:
            self._close(c, "송신 오류 %s" % (e.args[0] if e.args else e))

    def poll(self):
        """새 연결 수락과 연결별 요청 처리를 1회 수행함. 블로킹하지 않음."""
        if self._lsock is None:
            return
        now = ticks_ms()
        self._accept(now)
        for c in list(self._clients):
            self._service(c, now)
