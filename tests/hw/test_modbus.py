# Modbus RTU(RS485)·TCP 슬레이브 보드 통합 시험 — 원본: modbus/uModBusTCPSlave.py, modbus/main.py
#
# 실행: 보드에 modbus.py와 tests/hw/test_eth.py를 복사한 뒤
#   mpremote cp modbus.py :modbus.py
#   mpremote cp tests/hw/test_eth.py :test_eth.py
#   mpremote run tests/hw/test_modbus.py
# PC 측 확인:
#   TCP: python3 tools/mb_tcp_check.py 192.168.0.100
#   RTU: 9600 8N1, Unit ID 255로 Modbus 마스터 프로그램에서 FC01~06·0F·10 확인
# 판정: mb_tcp_check.py 실패 0건, 쓰기 시 LED·릴레이·DAC 출력이 실제로 바뀜
#       LED_04~07은 RELAY1~4 상태를 따라 점등됨(modbus.DataMap.sync_relay_leds)
#
# 원본과의 차이:
#   - 블로킹 accept/recv와 1000개 배열 대신 비차단 슈퍼루프와 데이터맵 크기만 사용
#   - 하드웨어 타이머 콜백 데이터 갱신 대신 슈퍼루프에서 주기 갱신(IRQ 내 할당 없음)
#
# 가정값(프로토콜 문서로 확인 필요):
#   - DI 값: 스위치 ON(핀 0) → 1
#   - IR0·IR1: ADC 12비트 원시값(0~4095), 공학 단위 환산 미적용
import time
import pyb
from machine import ADC, Pin, UART

import modbus

LED_NAMES = ("LED_01", "LED_02", "LED_03", "LED_04", "LED_05",
             "LED_06", "LED_07", "LED_08", "LED_09")
RELAY_NAMES = ("RELAY1", "RELAY2", "RELAY3", "RELAY4")
RTU_BAUD = 9600  # 가정값
INPUT_PERIOD_MS = 100


class BoardIO:
    """DataMap과 보드 입출력을 동기화함(시험용)."""

    def __init__(self, dm):
        self.dm = dm
        self.leds = [Pin(n, Pin.OUT, value=1) for n in LED_NAMES]
        self.relays = [Pin(n, Pin.OUT, value=0) for n in RELAY_NAMES]
        self.sws = [Pin("SW1", Pin.IN), Pin("SW2", Pin.IN)]
        self.adc = [ADC(Pin("ADC_VOLTAGE")), ADC(Pin("ADC_CURRENT"))]
        self.dac = pyb.DAC(1, bits=12)
        self.apply_outputs()
        self.read_inputs()

    def apply_outputs(self):
        c = self.dm.coils
        for i, led in enumerate(self.leds):
            led.value(0 if c[i] else 1)  # 액티브 로우
        for i, r in enumerate(self.relays):
            r.value(1 if c[9 + i] else 0)
        self.dac.write(self.dm.dac)

    def read_inputs(self):
        for i, sw in enumerate(self.sws):
            self.dm.di[i] = 0 if sw.value() else 1
        for i, a in enumerate(self.adc):
            self.dm.ir[i] = a.read_u16() >> 4

    def safe_off(self):
        for led in self.leds:
            led.value(1)
        for r in self.relays:
            r.value(0)
        self.dac.write(0)


def main(use_tcp=True, use_rtu=True, duration_ms=None):
    dm = modbus.DataMap()
    io = BoardIO(dm)
    rtu = None
    tcp = None
    if use_rtu:
        uart = UART(2, baudrate=RTU_BAUD, bits=8, parity=None, stop=1, timeout=0, rxbuf=512)
        rtu = modbus.RtuSlave(uart, dm, RTU_BAUD)
        print("Modbus RTU 시작: UART2 %d bps, Unit ID %d" % (RTU_BAUD, dm.unit_id))
    if use_tcp:
        from test_eth import eth_up

        if eth_up() is not None:
            tcp = modbus.TcpSlave(dm, port=502)
            tcp.start()
        else:
            print("이더넷 연결 실패: TCP 시험 생략")

    t0 = time.ticks_ms()
    t_in = t0
    try:
        while duration_ms is None or time.ticks_diff(time.ticks_ms(), t0) < duration_ms:
            now = time.ticks_ms()
            if time.ticks_diff(now, t_in) >= INPUT_PERIOD_MS:
                t_in = now
                io.read_inputs()
            if rtu:
                rtu.poll()
            if tcp:
                tcp.poll()
            if dm.changed:
                if dm.changed & modbus.CHG_UNIT_ID:
                    print("Unit ID 변경: %d (이 시험에서는 저장하지 않음)" % dm.unit_id)
                dm.changed = 0
                io.apply_outputs()
    finally:
        if tcp:
            tcp.stop()
        io.safe_off()
        if rtu:
            print("RTU 통계: 프레임 %d, CRC 오류 %d, 폐기 %d" % (rtu.rx_frames, rtu.crc_errors, rtu.dropped))
        print("Modbus 시험 종료: 출력 전부 OFF")


if __name__ == "__main__":
    main()
