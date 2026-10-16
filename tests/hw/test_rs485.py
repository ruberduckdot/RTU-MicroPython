# RS485(UART2, MAX13488 자동 방향 제어) 송수신 시험 — 원본: RS485.py
#
# 실행: mpremote run tests/hw/test_rs485.py
# 준비: USB-RS485 변환기를 A/B에 연결하고 PC 터미널을 9600 8N1로 엶
# 판정: PC 터미널에 1 초마다 "RTU-MCU RS485 TEST n"이 수신되고, PC에서 보낸
#       데이터가 콘솔에 출력됨. 수신 데이터는 그대로 되돌려 보냄(에코)
# 통신 속도 9600 bps는 가정값임(현장 설정에 맞게 변경)
import time
from machine import UART

BAUD = 9600


def main(duration_ms=30000, period_ms=1000):
    uart = UART(2, baudrate=BAUD, bits=8, parity=None, stop=1, timeout=0, rxbuf=256)
    buf = bytearray(64)
    n_tx = 0
    t0 = time.ticks_ms()
    t_next = t0
    print("RS485 시험 시작: %d bps, %d 초" % (BAUD, duration_ms // 1000))
    while time.ticks_diff(time.ticks_ms(), t0) < duration_ms:
        now = time.ticks_ms()
        if uart.any():
            k = uart.readinto(buf)
            if k:
                data = bytes(buf[:k])
                print("수신 %d 바이트: %r" % (k, data))
                uart.write(data)
        if time.ticks_diff(now, t_next) >= 0:
            t_next = time.ticks_add(now, period_ms)
            n_tx += 1
            uart.write(("RTU-MCU RS485 TEST %d\r\n" % n_tx).encode())
    print("RS485 시험 종료: 송신 %d 회" % n_tx)


if __name__ == "__main__":
    main()
