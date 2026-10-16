# 릴레이 출력(RELAY1~4) 순차 동작 시험 — 원본: DO.py
#
# 실행: mpremote run tests/hw/test_do.py
# 판정: RELAY1→4 순서로 1개씩 약 0.5 s ON(동작음·접점 도통 확인) 후 전부 OFF
# 주의: 릴레이에 부하가 연결되어 있으면 분리하고 시험함
import time
from machine import Pin

RELAY_NAMES = ("RELAY1", "RELAY2", "RELAY3", "RELAY4")  # High = ON


def main(cycles=2, on_ms=500):
    relays = [Pin(n, Pin.OUT, value=0) for n in RELAY_NAMES]
    try:
        for c in range(cycles):
            for name, r in zip(RELAY_NAMES, relays):
                r.value(1)
                print("[%d/%d] %s ON" % (c + 1, cycles, name))
                t0 = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), t0) < on_ms:
                    pass
                r.value(0)
                print("[%d/%d] %s OFF" % (c + 1, cycles, name))
    finally:
        for r in relays:
            r.value(0)
    print("릴레이 시험 종료: 전부 OFF")


if __name__ == "__main__":
    main()
