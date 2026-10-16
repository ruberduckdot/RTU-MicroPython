# LED_01~09 점등 시험 — 원본: led_flash.py
#
# 실행: mpremote run tests/hw/test_led.py
# 판정: LED_01→09 순서로 1개씩 점등(약 300 ms) 후, 전체 점멸 2회, 마지막에 전부 소등
# LED는 Low = 점등(액티브 로우)
import time
from machine import Pin

LED_NAMES = ("LED_01", "LED_02", "LED_03", "LED_04", "LED_05",
             "LED_06", "LED_07", "LED_08", "LED_09")


def _wait_ms(ms):
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        pass


def _set(led, on):
    led.value(0 if on else 1)


def main(step_ms=300):
    leds = [Pin(n, Pin.OUT, value=1) for n in LED_NAMES]  # 초기 소등
    try:
        for name, led in zip(LED_NAMES, leds):
            _set(led, True)
            print("%s 점등" % name)
            _wait_ms(step_ms)
            _set(led, False)
        for i in range(2):
            for led in leds:
                _set(led, True)
            print("전체 점등 %d" % (i + 1))
            _wait_ms(step_ms)
            for led in leds:
                _set(led, False)
            _wait_ms(step_ms)
    finally:
        for led in leds:
            _set(led, False)
    print("LED 시험 종료: 전부 소등")


if __name__ == "__main__":
    main()
