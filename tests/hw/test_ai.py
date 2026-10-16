# 아날로그 입력(ADC_VOLTAGE, ADC_CURRENT)과 DAC 출력(DAC_OUT) 시험 — 원본: AI.py
#
# 실행: mpremote run tests/hw/test_ai.py
# 판정:
#   1) DAC_OUT(PA4) 전압을 멀티미터로 측정해 단계별 기대값과 비교함
#   2) ADC 입력 핀에 기지 전압(0~3.3 V)을 인가하고 출력값과 비교함
# 환산은 기준 전압 3.3 V 가정값임(VREF+ 실측값으로 보정 필요). 전압·전류의
# 공학 단위 환산(분압비·션트)은 회로 확인 전이라 이 시험에서 다루지 않음.
import time
import pyb
from machine import ADC, Pin

VREF_MV = 3300  # 가정값
DAC_STEPS = (0, 1024, 2048, 3072, 4095)


def _wait_ms(ms):
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        pass


def _read(adc, n=16):
    s = 0
    for _ in range(n):
        s += adc.read_u16()
    return s // n


def main(step_ms=2000):
    adc_v = ADC(Pin("ADC_VOLTAGE"))
    adc_i = ADC(Pin("ADC_CURRENT"))
    dac = pyb.DAC(1, bits=12)  # DAC 채널 1 = DAC_OUT(PA4)
    try:
        for code in DAC_STEPS:
            dac.write(code)
            _wait_ms(step_ms)
            rv = _read(adc_v)
            ri = _read(adc_i)
            print("DAC=%4d (기대 %4d mV) | ADC_VOLTAGE raw=%5d %4d mV | ADC_CURRENT raw=%5d %4d mV" % (
                code, code * VREF_MV // 4095,
                rv, rv * VREF_MV // 65535,
                ri, ri * VREF_MV // 65535))
    finally:
        dac.write(0)
    print("AI/DAC 시험 종료: DAC=0")


if __name__ == "__main__":
    main()
