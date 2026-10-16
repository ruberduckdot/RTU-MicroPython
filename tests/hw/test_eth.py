# WIZ550io(W5500) 이더넷 연결 시험 — 원본: eth.py
#
# 실행: mpremote run tests/hw/test_eth.py
# 판정: "링크 연결됨"과 설정한 고정 IP가 출력되고, PC에서 ping 응답이 옴
#
# 원본과의 차이:
#   - ESP32 전용 network.LAN(PHY_W5500) 대신 stm32 포트의 network.WIZNET5K 사용
#     (보드 빌드: MICROPY_PY_NETWORK_WIZNET5K=5500, MICROPY_PY_LWIP=1 → lwIP MACRAW)
#   - GPIO 번호 대신 pins.csv 별칭(WIZ_CS, WIZ_RST, WIZ_INT, WIZ_READY) 사용
#   - time.time() 초 단위 대기 대신 ticks_ms 기반 시간 제한
#   - 임의 MAC 강제 설정과 TCP 클라이언트 무한 루프는 반영하지 않음
import time
import network
from machine import Pin, SPI

# 고정 IP 설정(가정값, 현장 네트워크에 맞게 변경)
IFCONFIG = ("192.168.0.100", "255.255.255.0", "192.168.0.1", "192.168.0.1")
SPI_BAUD = 10_000_000  # 가정값: SPI3(APB1 42 MHz) 분주 시 이 값 이하로 설정됨


def _fmt_mac(mac):
    return ":".join("%02x" % b for b in mac)


def eth_up(ifconfig=IFCONFIG, link_timeout_ms=10000):
    """W5500을 초기화하고 고정 IP를 설정한 뒤 링크를 기다림.

    성공하면 WIZNET5K 객체를, 시간 안에 링크가 안 잡히면 None을 반환함.
    부팅 시 1회 호출하는 초기화 함수이며 최대 link_timeout_ms 동안 대기함.
    """
    spi = SPI(3, baudrate=SPI_BAUD, polarity=0, phase=0)
    nic = network.WIZNET5K(spi, Pin("WIZ_CS"), Pin("WIZ_RST"), Pin("WIZ_INT"))
    nic.active(True)  # 내부에서 WIZ_RST 펄스 후 약 410 ms 대기함
    rdy = Pin("WIZ_READY", Pin.IN)
    print("WIZ_READY=%d, MAC=%s" % (rdy.value(), _fmt_mac(nic.config("mac"))))
    nic.ifconfig(ifconfig)

    t0 = time.ticks_ms()
    t_log = t0
    while not nic.isconnected():
        now = time.ticks_ms()
        if time.ticks_diff(now, t0) >= link_timeout_ms:
            print("링크 대기 시간 초과(%d ms): 케이블·허브 확인, status=%d" % (link_timeout_ms, nic.status()))
            return None
        if time.ticks_diff(now, t_log) >= 1000:
            t_log = now
            print("링크 대기 중... status=%d (0=링크 없음, 1=링크만, 2=활성)" % nic.status())
    print("링크 연결됨: %d ms" % time.ticks_diff(time.ticks_ms(), t0))
    print("IP 설정: %s / %s, GW %s, DNS %s" % nic.ifconfig())
    return nic


def main():
    nic = eth_up()
    if nic is None:
        print("이더넷 시험 실패")
        return
    print("이더넷 시험 대기: PC에서 ping %s 확인" % IFCONFIG[0])


if __name__ == "__main__":
    main()
