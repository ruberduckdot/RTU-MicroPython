# 외부 업체 샘플 소스 검토 결과 (02_Sources)

- 검토 대상: `reference/02_Sources/`. 업체가 제공한 ESP32-S3용 MicroPython 샘플이며 .py 파일 21개임. 이 폴더는 커밋하지 않음(`.gitignore`).
- 적용 대상: IOTPLUS RTU MCU R1.0a(EDGEON EG-C08A), STM32F429, MicroPython stm32 포트(공식 master), 보드 정의 `RTU_MCU_R10`
- API 확인 기준: MicroPython 공식 master 커밋 `9e348d293c`(v1.30.0-preview)의 `ports/stm32`·`extmod` 소스. 보드 정의는 사용자가 첨부한 `mpconfigboard.h/.mk`, `pins.csv`, `stm32f429_af.csv`를 기준으로 함. 보드 정의 파일은 수정하지 않았고 이 레포에 커밋하지도 않음.
- 전제: 레포에는 1단계 파일(config.py, hw.py, modbus.py, setproto.py, main.py, test_hw.py)이 없었음. 그래서 기존 파일과 비교하는 대신 신규로 작성함. 이후 1단계 파일과 병합할 때 `modbus.py`의 이름과 역할이 겹치는지 확인이 필요함.
- 실보드 시험: **미실시**. 이 문서의 산출물은 모두 "호스트 시험 통과" 상태임. "실보드 검증 완료" 상태가 아님.

---

## 1. 파일별 판정표 (21개)

| # | 원본 파일 | 판정 | 근거(우리 회로·포트 기준) |
|---|---|---|---|
| 1 | `AI.py` | 부분 적용 | ADC 주기 읽기 패턴만 사용함. `ADC.atten()`은 ESP32 전용이고, 4~20 mA/150 Ω 환산은 우리 회로(0~3.3 V 직접 입력)와 맞지 않음. 원본은 정의되지 않은 변수 `val_raw2` 때문에 NameError가 발생함 |
| 2 | `DI.py` | 부분 적용 | 입력 폴링 패턴만 사용함. SW1·SW2는 외부 10 kΩ 풀업(ON = 0)이므로 원본의 `PULL_DOWN`은 쓰지 않음 |
| 3 | `DO.py` | 부분 적용 | 원본은 DO 2채널(GPIO15/16)임. 우리 보드의 RELAY1~4(High = ON)로 바꾸고, `sleep` 대신 ticks 기반 대기를 사용함 |
| 4 | `led_flash.py` | 부분 적용 | 원본은 LED 2개(GPIO45/21, High = 점등)임. 우리 보드는 LED_01~09이고 Low = 점등임 |
| 5 | `RS485.py` | 부분 적용 | UART 송수신 패턴만 사용함. stm32 UART2는 핀이 보드에 고정(PA2/PA3)되어 있어 `tx=`/`rx=`를 지정하지 않음. 방향 제어는 MAX13488이 자동으로 함 |
| 6 | `RS232.py` | 적용 불가 | RS232 트랜시버가 실장되어 있지 않음. USART1은 CH340C를 거쳐 REPL과 설정 프로그램이 함께 쓰므로 시험 스크립트가 점유하면 REPL이 끊김. 코드도 RS485.py와 같음 |
| 7 | `eth.py` | 부분 적용 | `network.LAN(PHY_W5500)`은 ESP32 전용이므로 stm32의 `network.WIZNET5K`로 바꿈. 연결·고정 IP·링크 대기·타임아웃 패턴만 반영함. MAC 강제 설정과 TCP 클라이언트 무한 루프는 반영하지 않음. 원본에는 정의되지 않은 변수 `client_socket` 결함이 있음 |
| 8 | `wlan_tcp.py` | 적용 불가 | WLAN 하드웨어가 없음. 블로킹 소켓을 쓰는 무한 루프 TCP 클라이언트라 슈퍼루프 구조와 맞지 않음 |
| 9 | `4g.py` | 적용 불가 | 4G 모뎀이 실장되어 있지 않음. 4G 기능은 범위 밖임 |
| 10 | `lora.py` | 적용 불가 | LoRa 모듈이 실장되어 있지 않음. LoRa 기능은 범위 밖임 |
| 11 | `sdcard.py` | 적용 불가 | SD 슬롯이 실장되어 있지 않음(`MICROPY_HW_ENABLE_SDCARD (0)`). `machine.SDCard(slot=2)`는 ESP32 API임 |
| 12 | `sdcard_speed.py` | 적용 불가 | 11번과 같은 이유임 |
| 13 | `ble_advertising.py` | 적용 불가 | BLE 하드웨어가 없음(STM32F429에 무선 기능 없음) |
| 14 | `ble_simple_central.py` | 적용 불가 | 13번과 같은 이유임 |
| 15 | `ble_simple_peripheral.py` | 적용 불가 | 13번과 같은 이유임 |
| 16 | `mqtt/mqtt_onenet_eth.py` | 적용 불가 | MQTT·클라우드는 범위 밖임. `_thread`(사용 금지)를 쓰고, micropython-lib의 `umqtt`(외부 의존성)가 필요함 |
| 17 | `modbus/main.py` | 부분 적용 | TCP 마스터 연결과 재시도 패턴만 PC 도구(`tools/mb_tcp_check.py`)의 연결 실패 처리에 반영함. 그 밖의 W5500 초기화 부분은 ESP32 전용임 |
| 18 | `modbus/uModBusConst.py` | 부분 적용 | 기능 코드·예외 코드 값과 CRC 다항식(0xA001)만 참고함. 이 값들은 Modbus 규격 값이고, 코드와 CRC 테이블은 복사하지 않음. 테이블은 생성식으로 런타임에 만듦 |
| 19 | `modbus/uModBusFunctions.py` | 부분 적용 | 요청 PDU 구성 동작을 참고해 PC 도구에서 새로 작성함. 원본 FC0F 바이트 수 계산(`len//8 + 1`)은 수량이 8의 배수일 때 틀리므로 사용하지 않음 |
| 20 | `modbus/uModBusTCPPoll.py` | 부분 적용 | TCP 마스터를 `tools/mb_tcp_check.py`(CPython 표준 라이브러리만 사용)로 재작성함. 원본 결함 3가지가 있음: `recv(256)`을 1회만 호출해 부분 수신을 처리하지 못함, 예외 응답을 `ValueError` 문자열로만 알림, 응답 길이를 검증하지 않음 |
| 21 | `modbus/uModBusTCPSlave.py` | 부분 적용 | 슬레이브 동작(FC 분기, 예외 응답)을 참고해 `modbus.py`에 새로 작성함. 원본 결함은 2절의 비교표에 정리함 |

집계: 적용 0개, 부분 적용 11개, 적용 불가 10개, 합계 21개.

---

## 2. Modbus 슬레이브 비교 (원본 `uModBusTCPSlave.py`와 `modbus.py` 비교)

| 항목 | 업체 원본 | `modbus.py` 반영 내용 |
|---|---|---|
| 데이터 영역 | Coil·DI·HR·IR 각 1000개 배열(약 수십 KB) | 데이터맵 크기만 사용함: Coil 13, DI 2, HR 16, IR 2 |
| 동작 구조 | 블로킹 `accept()` → 한 클라이언트를 처리하는 동안 다른 처리가 모두 멈춤 | 비차단 `poll()`. 최대 2개 연결, 초과 연결은 즉시 닫음 |
| MBAP 검증 | 프로토콜 ID와 길이를 검증하지 않음 | 프로토콜 ID ≠ 0 또는 길이가 2~254를 벗어나면 연결을 닫음(스트림 재동기화 불가) |
| 부분 수신 | `recv(7)`·`recv(length-1)`가 요청한 길이만큼 온다고 가정함 | `MbapReader`가 바이트 단위로 누적함. 분할 수신 시험 통과 |
| 다중 요청 | 1회 recv에 요청이 2개 붙어 오면 두 번째 요청이 깨짐 | 수신 버퍼의 완결 ADU를 모두 순서대로 처리함. 파이프라이닝 시험 통과 |
| Unit ID | 불일치하면 예외 02(주소 오류)를 반환함 | 자국 ID, 0xFF, 0은 응답하고, 그 외에는 예외 0x0B를 반환함 [가정, 6절] |
| 예외 응답 | 처리 중 예외가 나면 일괄 03을 반환함. FC06은 값을 검사하지 않음 | 규격 순서(FC → 수량·길이 → 주소 → 값)로 01·02·03을 구분함. HR0 > 4095, HR15 ∉ 248~255, HR1 쓰기를 모두 거부함 |
| FC10 원자성 | 값마다 바로 반영함 | 모든 값을 검사한 뒤 일괄 반영함. 하나라도 오류면 아무것도 반영하지 않음 |
| PDU 길이 | 검사하지 않음(바이트가 남거나 모자라도 처리함) | 기능 코드별 정확한 길이가 아니면 03을 반환함 |
| 데이터 갱신 | `machine.Timer(0)` 콜백에서 갱신함 | 슈퍼루프에서 주기적으로 갱신함. 하드 IRQ 안에서 메모리를 할당하지 않음 |
| RTU | 없음(TCP 전용) | `RtuSlave`를 추가함. 기능 코드별 길이와 CRC로 프레임을 분리하고, 무신호 시간 ≥ max(t3.5, 5 ms)이면 미완성 프레임을 폐기함. 브로드캐스트(주소 0)는 쓰기만 실행하고 응답하지 않음 |

RTU 프레임을 길이 기반으로 분리한 이유: MicroPython 슈퍼루프에서는 GC나 소켓 처리 때문에 poll 간격이 3.5문자 시간(9600 bps에서 4.01 ms)보다 길어질 수 있음. 이때 문자 사이 간격만으로 프레임을 나누면 정상 프레임을 잘못 폐기할 수 있음. 그래서 기대 길이와 CRC를 우선으로 판단하고, 무신호 시간은 쓰레기 바이트를 정리하는 데만 사용함.

---

## 3. 반영 내역 (원본 → 산출 파일)

| 원본 | 산출 파일 | 내용 |
|---|---|---|
| `DO.py` | `tests/hw/test_do.py` | RELAY1~4 순차 ON/OFF, 종료 시 전부 OFF |
| `led_flash.py` | `tests/hw/test_led.py` | LED_01~09 순차 점등과 전체 점멸(액티브 로우) |
| `DI.py` | `tests/hw/test_di.py` | SW1·SW2 상태가 바뀔 때 출력(50 ms 폴링, 20 s 동안) |
| `AI.py` | `tests/hw/test_ai.py` | ADC_VOLTAGE·ADC_CURRENT를 `read_u16()` 16회 평균으로 읽음. DAC_OUT 5단계 출력(`pyb.DAC(1, bits=12)`) |
| `RS485.py` | `tests/hw/test_rs485.py` | UART2 9600 8N1. 1 s 주기로 송신하고 수신 데이터를 에코함. 30 s 동안 실행 |
| `eth.py` | `tests/hw/test_eth.py` | `network.WIZNET5K(SPI(3), WIZ_CS, WIZ_RST, WIZ_INT)`, 고정 IP, 10 s 링크 대기 제한, `eth_up()` 제공 |
| `modbus/uModBusTCPSlave.py`, `modbus/uModBusConst.py` | `modbus.py` | CRC-16, `DataMap`, `process_pdu`, `RtuSlave`, `MbapReader`, `TcpSlave` |
| `modbus/uModBusTCPSlave.py`, `modbus/main.py` | `tests/hw/test_modbus.py` | 보드 통합 시험(RTU + TCP 동시 실행, 입출력 동기화) |
| `modbus/uModBusTCPPoll.py`, `modbus/uModBusFunctions.py`, `modbus/main.py` | `tools/mb_tcp_check.py` | PC 측 왕복 시험 29개 항목(FC01~06·0F·10, 예외 01/02/03, 파이프라이닝, 분할 송신, Unit ID 0xFF) |
| (신규) | `tests/host/test_crc.py`, `test_pdu.py`, `test_rtu.py`, `test_tcp.py` | CPython 단위 시험 45개 |
| (신규) | `.github/workflows/firmware-check.yml` | mpy-cross 컴파일과 호스트 단위 시험 |

### 3.1 사용한 stm32 API와 확인 근거

| API | 확인 위치(MicroPython `9e348d293c`) |
|---|---|
| `network.WIZNET5K(spi, cs, rst[, int])` | `extmod/network_wiznet5k.c`. lwIP 빌드에서 인자 3~4개를 받음 |
| `.active()`, `.isconnected()`, `.status()`, `.ifconfig()`, `.config('mac')` | 같은 파일의 locals 표. lwIP 빌드의 `isconnected()`는 PHY 링크, 활성 상태, IP ≠ 0을 모두 만족해야 True임 |
| `machine.ADC(Pin).read_u16()` | `ports/stm32/machine_adc.c`. Pin 객체로 생성할 수 있고 12비트 설정임 |
| `pyb.DAC(1, bits=12).write()` | `ports/stm32/dac.c` |
| `machine.UART(2, ..., timeout, rxbuf)`, `.any()`, `.readinto()` | `ports/stm32/machine_uart.c`, `extmod/machine_uart.c` |
| `machine.Pin(name, mode, value=)` | `ports/stm32/pin.c` |
| `socket.setblocking(False)`, `SO_REUSEADDR`, 비차단에서 `OSError(EAGAIN)` 발생 | `extmod/modlwip.c` |
| `time.ticks_ms/ticks_us/ticks_diff/ticks_add` | `extmod/modtime.c` |

사용하지 않은 API: `ADC.read_uv()`는 stm32 포트에서 `MICROPY_PY_MACHINE_ADC_READ_UV`가 켜져 있는지 확인하지 못해 사용하지 않음. `ADC.atten()`은 ESP32 전용임.

---

## 4. 적용 불가 목록

| 원본 | 사유 |
|---|---|
| `RS232.py` | RS232 트랜시버가 실장되어 있지 않음. USART1은 REPL·설정 프로그램이 함께 씀 |
| `wlan_tcp.py` | WLAN 하드웨어가 없음 |
| `4g.py` | 4G 모뎀이 실장되어 있지 않음. 기능 범위 밖임 |
| `lora.py` | LoRa 모듈이 실장되어 있지 않음. 기능 범위 밖임 |
| `sdcard.py`, `sdcard_speed.py` | SD 슬롯이 실장되어 있지 않음. `MICROPY_HW_ENABLE_SDCARD (0)` |
| `ble_advertising.py`, `ble_simple_central.py`, `ble_simple_peripheral.py` | BLE 하드웨어가 없음 |
| `mqtt/mqtt_onenet_eth.py` | MQTT·클라우드는 범위 밖임. `_thread`와 `umqtt` 외부 의존성이 필요함. 소스에 인증 토큰 형식의 문자열(일부 마스킹)이 들어 있으므로 외부에 전달할 때 주의해야 함 |

---

## 5. 라이선스 확인 결과

| 대상 | 결과 | 조치 |
|---|---|---|
| `modbus/uModBusConst.py`, `uModBusFunctions.py`, `uModBusTCPPoll.py` | 파일 머리에 "Source: github.com/pycom/pycom-modbus"가 표기되어 있음. 원 저장소(`pycom/pycom-modbus`, 최종 커밋 `e029a399`, 2020-12-11)의 파일 머리에 "GNU GPL version 3 or any later version, with permitted additional terms (Pycom Licence v1.0)"가 명시되어 있음. 업체 사본에는 이 라이선스 문구가 빠져 있음 | 코드·CRC 테이블을 복사하지 않음. 규격(Modbus Application Protocol V1.1b3, Modbus over Serial Line V1.02)을 기준으로 새로 작성함. 기능 코드·예외 코드 값과 CRC 다항식은 규격에 정해진 값임 |
| `modbus/uModBusTCPSlave.py`, `modbus/main.py` | 라이선스 표기가 없음. pycom 모듈을 import하는 업체 작성 코드로 보임 | 동작만 참고하고 새로 작성함 |
| `ble_*.py` | MicroPython 공식 예제(MIT)와 같은 형태로 보임 [미확인] | 적용 불가라 사용하지 않음 |
| 나머지 주변장치 예제 | 라이선스 표기 없음 | 동작만 참고하고 새로 작성함(GPIO 번호·주석은 옮기지 않음) |

---

## 6. 미확인 사항과 가정값

| # | 항목 | 현재 처리 | 확인 방법 |
|---|---|---|---|
| 1 | `mpconfigboard.h` 주석이 서로 상충함: "SW2 is wired to NRST"와 "SW1/SW2 = PD14/PD15" | `pins.csv` 별칭 `SW1`/`SW2`(PD14/PD15)를 사용함 | 회로도 IOTPLUS-SCH-RTU-MCU Rev 1.0에서 SW2 결선을 확인. 보드 정의 주석 정정 여부는 별도로 결정 |
| 2 | HR1 비트 배치 | bit n = Coil n(bit0~8 LED01~09, bit9~12 Relay01~04) [가정] | 프로토콜 20260928 문서 확인 |
| 3 | HR2~14(예약 영역) 동작 | 읽으면 0, 쓰면 예외 02 [가정] | 프로토콜 문서 확인 |
| 4 | DI 값 극성 | 스위치 ON(핀 0)이면 DI = 1 [가정, `tests/hw/test_modbus.py`] | 프로토콜 문서 확인 |
| 5 | IR0·IR1 단위·스케일 | ADC 12비트 원시값(0~4095) [가정]. 분압비·션트 환산 미적용 | 회로도의 아날로그 전단 확인 |
| 6 | ADC 기준 전압 | 3.3 V [가정] | VREF+ 실측 |
| 7 | RS485 통신 조건 | 9600 bps 8N1 [가정] | 프로토콜 문서와 설정 프로그램 확인 |
| 8 | TCP Unit ID 정책 | 자국 ID·0xFF·0은 응답, 그 외에는 예외 0x0B [가정] | 프로토콜 문서와 상위 SCADA 설정 확인 |
| 9 | Unit ID 범위 248~255 | 데이터맵대로 유지함. Modbus 시리얼 규격에서 개별 주소는 1~247이고 248~255는 예약 범위임. 일부 RTU 마스터가 248 이상의 주소를 거부할 수 있음 | 현장 마스터 장비로 확인 |
| 10 | Unit ID 변경 저장 | `DataMap.changed`의 `CHG_UNIT_ID` 비트로 알리기만 함. 저장은 1단계 `config.py`가 없어 구현하지 않음 | 1단계 파일과 병합할 때 연결 |
| 11 | SPI3 클럭 | 10 MHz 이하 [가정] | WIZ550io 데이터시트 최대 클럭 확인 후 실보드에서 통신 안정성 확인 |
| 12 | `WIZ_INT` 인터럽트 모드 | `network.WIZNET5K`에 4번째 인자로 전달함(소스상 지원) | 실보드에서 수신 지연과 누락 여부 확인 |
| 13 | lwIP 비차단 `send()`의 부분 송신 | 응답이 잘리면 연결을 닫음 | 실보드 부하 시험 |
| 14 | `ADC.read_uv()` 지원 여부 | 사용하지 않음 | stm32 `mpconfigport.h`와 실보드에서 확인 |
| 15 | `mpconfigboard.mk`의 `FROZEN_MANIFEST = $(BOARD_DIR)/manifest.py` | 첨부 zip에 `manifest.py`가 없음 | 보드 디렉터리 원본 확인 |

---

## 7. 검증 내역

| 검증 | 명령 | 결과 |
|---|---|---|
| mpy-cross 컴파일 | `mpy-cross -o <out>.mpy <file>.py` (레포의 .py 전체) | 14개 파일 통과 |
| 호스트 단위 시험(CPython 3.13) | `python3 -m unittest discover -s tests/host -v` | 45개 통과 |
| TCP 루프백(CPython 슬레이브) | `test_tcp.LoopbackTest.test_full_check` | `mb_tcp_check` 29개 항목 통과 |
| TCP 루프백(MicroPython unix 포트 슬레이브, 참고) | unix 포트에서 `modbus.TcpSlave` 실행 후 `python3 tools/mb_tcp_check.py 127.0.0.1 --port 15021` | 29개 통과, 실패 0. stm32/lwIP가 아니므로 실보드 검증을 대신하지 못함 |
| 실보드 | `tests/hw/*.py`, `tools/mb_tcp_check.py <보드 IP>` | **미실시** |

### 7.1 실보드 확인 절차 (권장 순서)

1. 개발 모드로 부팅함(SW1·SW2 ON). `mpremote run tests/hw/test_led.py`, `test_do.py`, `test_di.py`, `test_ai.py`를 차례로 실행함
2. USB-RS485 변환기를 연결하고 `mpremote run tests/hw/test_rs485.py`를 실행함
3. LAN 케이블을 연결하고 `mpremote run tests/hw/test_eth.py`를 실행한 뒤 PC에서 ping을 확인함
4. `mpremote cp modbus.py :modbus.py` → `mpremote cp tests/hw/test_eth.py :test_eth.py` → `mpremote run tests/hw/test_modbus.py`를 실행함
5. PC에서 `python3 tools/mb_tcp_check.py 192.168.0.100`을 실행함. 실패 0건이어야 하고, 쓰기 시험 중 LED·릴레이·DAC가 실제로 바뀌어야 함
6. RTU는 Modbus 마스터 프로그램(9600 8N1, Unit ID 255)으로 FC01~06·0F·10과 예외 응답을 확인함
