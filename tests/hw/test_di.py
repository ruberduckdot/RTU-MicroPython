# DIP 스위치 입력(SW1, SW2) 시험 — 원본: DI.py
#
# 실행: mpremote run tests/hw/test_di.py
# 판정: 스위치를 조작할 때마다 변화가 출력되고, ON = 0 / OFF = 1로 읽힘
# 회로: 외부 10 kΩ 풀업이 있으므로 내부 풀업·풀다운을 쓰지 않음
# 주의: 부팅 시 SW1·SW2가 모두 ON이면 개발 모드(REPL 유지)로 동작함
import time
from machine import Pin

SW_NAMES = ("SW1", "SW2")


def main(duration_ms=20000, period_ms=50):
    sws = [Pin(n, Pin.IN) for n in SW_NAMES]
    last = None
    t0 = time.ticks_ms()
    t_next = t0
    print("DI 시험 시작: %d 초 동안 스위치를 조작함" % (duration_ms // 1000))
    while time.ticks_diff(time.ticks_ms(), t0) < duration_ms:
        now = time.ticks_ms()
        if time.ticks_diff(now, t_next) < 0:
            continue
        t_next = time.ticks_add(now, period_ms)
        cur = tuple(s.value() for s in sws)
        if cur != last:
            print("SW1=%d(%s) SW2=%d(%s)" % (
                cur[0], "ON" if cur[0] == 0 else "OFF",
                cur[1], "ON" if cur[1] == 0 else "OFF"))
            last = cur
    print("DI 시험 종료")


if __name__ == "__main__":
    main()
