# 외부 업체 샘플 소스 검토 결과 (02_Sources)

- 검토 대상: `reference/02_Sources/`. 업체가 제공한 ESP32-S3용 MicroPython 샘플이며 .py 파일 21개임. 이 폴더는 커밋하지 않음(`.gitignore`).
- 적용 대상: IOTPLUS RTU MCU R1.0a(EDGEON EG-C08A), STM32F429, MicroPython stm32 포트(공식 master), 보드 정의 `RTU_MCU_R10`
- API 확인 기준: MicroPython 공식 master 커밋 `9e348d293c`(v1.30.0-preview)의 `ports/stm32`·`extmod` 소스. 보드 정의는 사용자가 첨부한 `mpconfigboard.h/.mk`, `pins.csv`, `stm32f429_af.csv`를 기준으로 함. 보드 정의 파일은 수정하지 않았고 이 레포에 커밋하지도 않음.
- 전제: 레포에는 1단계 파일(config.py, hw.py, modbus.py, setproto.py, main.py, test_hw.py)이 없었음. 그래서 기존 파일과 비교하는 대신 신규로 작성함. 이후 1단계 파일과 병합할 때 `modbus.py`의 이름과 역할이 겹치는지 확인이 필요함.
- 회로도 대조: IOTPLUS-SCH-RTU-MCU Rev 1.0(2026-08-21, 6쪽)으로 결선을 확인함. 결과는 6절과 8절에 반영함.
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
| 6 | `RS232.py` | 적용 불가 | RS232 트랜시버가 실장되어 있지 않음(회로도에서 확인, LED 실크의 "RS485 / RS232" 표기만 있음). USART1은 CH340C를 거쳐 REPL과 설정 프로그램이 함께 쓰므로 시험 스크립트가 점유하면 REPL이 끊김. 코드도 RS485.py와 같음 |
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
| `modbus/uModBusTCPPoll.py`, `modbus/uModBusFunctions.py`, `modbus/main.py` | `tools/mb_tcp_check.py` | PC 측 왕복 시험 31개 항목(FC01~06·0F·10, LED04~07 릴레이 연동, 예외 01/02/03, 파이프라이닝, 분할 송신, Unit ID 0xFF) |
| (신규) | `tests/host/test_crc.py`, `test_pdu.py`, `test_rtu.py`, `test_tcp.py` | CPython 단위 시험 49개 |
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
| `RS232.py` | RS232 트랜시버가 실장되어 있지 않음(회로도 확인). USART1은 REPL·설정 프로그램이 함께 씀 |
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
| 1 | ~~`mpconfigboard.h` 주석 상충~~ **해소**: "SW2 is wired to NRST"와 "SW1/SW2 = PD14/PD15" | 두 주석 모두 맞음. 이름이 겹친 것임. 부품 번호 SW2는 리셋 택트 스위치(TS-1105, NRST, R14 10 kΩ 풀업, C20 0.1 µF). pins.csv의 SW1/SW2는 DIP 스위치 SW1(DS02, 2극)의 1·2번 접점(넷 PD14_SW1, PD15_SW2)이며 외부 10 kΩ 풀업(R7·R8), ON = 0 | 회로도 2쪽에서 확인 완료. 보드 정의 주석 문구 정정 여부는 별도 결정(이번 작업에서는 수정하지 않음) |
| 2 | HR1 비트 배치 | bit n = Coil n(bit0~8 LED01~09, bit9~12 Relay01~04) [가정]. bit3~6은 LED04~07 연동에 따라 bit9~12와 같음 | 프로토콜 20260928 문서 확인 |
| 3 | HR2~14(예약 영역) 동작 | 읽으면 0, 쓰면 예외 02 [가정] | 프로토콜 문서 확인 |
| 4 | DI 값 극성 | 스위치 ON(핀 0)이면 DI = 1 [가정, `tests/hw/test_modbus.py`] | 프로토콜 문서 확인 |
| 5 | IR0·IR1 단위·스케일 | 회로 확인: 두 입력 모두 0~3.3 V 전압 입력이며 TLV9001 단위 이득 버퍼 → R 1 kΩ·C 0.1 µF(fc 1.59 kHz) → BAT54S 클램프를 거쳐 PA0/PA1로 들어감. 션트가 없어 IR1 "전류"는 외부 트랜스듀서가 내는 전압임(4~20 mA 직접 입력 불가). 레지스터 값은 ADC 12비트 원시값(0~4095) [가정] | 공학 단위 환산식은 외부 센서 사양과 프로토콜 문서로 확인 |
| 6 | ADC 기준 전압 | 회로 확인: VREF+ = VDDA(+3V3 → FB1 → R16 47 Ω, C21 1 µF + C22 0.1 µF), 즉 LD1117-3.3 출력이 기준임. 정확도는 LDO 편차를 따름 | VREF+ 실측. 보정에는 `machine.ADC(ADC.CORE_VREF)`(stm32 `machine_adc.c`에서 존재 확인)를 쓸 수 있음. VREFINT 교정값 주소는 [미확인] |
| 7 | RS485 통신 조건 | 9600 bps 8N1 [가정] | 프로토콜 문서와 설정 프로그램 확인 |
| 8 | TCP Unit ID 정책 | 자국 ID·0xFF·0은 응답, 그 외에는 예외 0x0B [가정] | 프로토콜 문서와 상위 SCADA 설정 확인 |
| 9 | Unit ID 범위 248~255 | 데이터맵대로 유지함. Modbus 시리얼 규격에서 개별 주소는 1~247이고 248~255는 예약 범위임. 일부 RTU 마스터가 248 이상의 주소를 거부할 수 있음 | 현장 마스터 장비로 확인 |
| 10 | Unit ID 변경 저장 | `DataMap.changed`의 `CHG_UNIT_ID` 비트로 알리기만 함. 저장은 1단계 `config.py`가 없어 구현하지 않음 | 1단계 파일과 병합할 때 연결 |
| 11 | SPI3 클럭 | 10 MHz 이하 [가정] | WIZ550io 데이터시트 최대 클럭 확인 후 실보드에서 통신 안정성 확인 |
| 12 | `WIZ_INT` 인터럽트 모드 | `network.WIZNET5K`에 4번째 인자로 전달함(소스상 지원) | 실보드에서 수신 지연과 누락 여부 확인 |
| 13 | lwIP 비차단 `send()`의 부분 송신 | 응답이 잘리면 연결을 닫음 | 실보드 부하 시험 |
| 14 | `ADC.read_uv()` 지원 여부 | 사용하지 않음 | stm32 `mpconfigport.h`와 실보드에서 확인 |
| 15 | `mpconfigboard.mk`의 `FROZEN_MANIFEST = $(BOARD_DIR)/manifest.py` | 첨부 zip에 `manifest.py`가 없음 | 보드 디렉터리 원본 확인 |
| 16 | DAC 출력 범위 | 회로 확인: PA4 → TLV9001 외부 버퍼 → R47 100 Ω → DAC_OUT(PESD3V3 보호). `pyb.DAC.write()`는 기본값으로 내부 출력 버퍼를 끔(stm32 `dac.c` 확인) → 0~VREF+ 전 범위 출력 | 실보드에서 0·4095 코드의 출력 전압 측정 |
| 17 | ~~LED_04~07 표시 동작~~ **결정됨(연동)** | 회로 실크 "RELAY 4CH"에 맞춰 Coil 3~6(LED04~07)이 Coil 9~12(Relay01~04) 상태를 항상 따라감(`modbus.RELAY_LED_COILS`, `DataMap.sync_relay_leds()`). Coil 3~6 쓰기(FC05·FC0F)는 정상 응답하되 값은 릴레이 상태로 덮어씀(예외 없음, FC0F 일괄 쓰기 호환). HR1 비트 3~6도 같은 값 | 프로토콜 문서 20260928에 연동 동작 반영 필요 |
| 18 | WIZ550io 초기화 타이밍 | 드라이버(`active(True)`)는 RDY를 보지 않고 리셋 해제 후 160 ms 고정 대기 후 접근함. 커뮤니티 문서 권고는 "RDY High 후 ≥ 150 ms" [미확인] | RSTn·RDY 파형 측정, `test_eth.py`가 출력한 MAC과 모듈 라벨 MAC 비교 |

---

## 7. 검증 내역

| 검증 | 명령 | 결과 |
|---|---|---|
| mpy-cross 컴파일 | `mpy-cross -o <out>.mpy <file>.py` (레포의 .py 전체) | 14개 파일 통과 |
| 호스트 단위 시험(CPython 3.13) | `python3 -m unittest discover -s tests/host -v` | 49개 통과 |
| TCP 루프백(CPython 슬레이브) | `test_tcp.LoopbackTest.test_full_check` | `mb_tcp_check` 31개 항목 통과 |
| TCP 루프백(MicroPython unix 포트 슬레이브, 참고) | unix 포트에서 `modbus.TcpSlave` 실행 후 `python3 tools/mb_tcp_check.py 127.0.0.1 --port 15022` | 31개 통과, 실패 0. stm32/lwIP가 아니므로 실보드 검증을 대신하지 못함 |
| 실보드 | `tests/hw/*.py`, `tools/mb_tcp_check.py <보드 IP>` | **미실시** |

### 7.1 실보드 확인 절차 (권장 순서)

1. 개발 모드로 부팅함(SW1·SW2 ON). `mpremote run tests/hw/test_led.py`, `test_do.py`, `test_di.py`, `test_ai.py`를 차례로 실행함
2. USB-RS485 변환기를 연결하고 `mpremote run tests/hw/test_rs485.py`를 실행함
3. LAN 케이블을 연결하고 `mpremote run tests/hw/test_eth.py`를 실행한 뒤 PC에서 ping을 확인함
4. `mpremote cp modbus.py :modbus.py` → `mpremote cp tests/hw/test_eth.py :test_eth.py` → `mpremote run tests/hw/test_modbus.py`를 실행함
5. PC에서 `python3 tools/mb_tcp_check.py 192.168.0.100`을 실행함. 실패 0건이어야 하고, 쓰기 시험 중 LED·릴레이·DAC가 실제로 바뀌어야 함
6. RTU는 Modbus 마스터 프로그램(9600 8N1, Unit ID 255)으로 FC01~06·0F·10과 예외 응답을 확인함

---

## 8. 회로도 대조 결과 (IOTPLUS-SCH-RTU-MCU Rev 1.0)

회로도만으로 판단한 결과임. 부품 정격 중 데이터시트로 확인하지 못한 값은 [미확인]으로 표시함. PCB 레이아웃(연면거리, 동박 면적)은 이 검토 범위가 아님.

### 8.1 핀 결선 대조 (pins.csv 별칭 기준)

| 별칭 | 회로도 넷 | 결과 |
|---|---|---|
| RELAY1~4 (PE7~PE10) | PE07_GPIO_1~PE10_GPIO_4 → R 1 kΩ → LTV-247 → MMBT3904 → HF32FA | 일치. High = ON |
| LED_01~09 | PB13_LED_01, PB14_LED_02, PB15_LED_03, PD08_LED_04~PD13_LED_09 → R 1 kΩ → LED 캐소드(애노드 +3V3) | 일치. Low = 점등 |
| SW1, SW2 (PD14, PD15) | PD14_SW1, PD15_SW2 → DIP SW1 → GND, 풀업 R7·R8 10 kΩ | 일치. ON = 0 |
| ADC_VOLTAGE, ADC_CURRENT (PA0, PA1) | PA00_ADC1_CH0, PA01_ADC2_CH1 ← 버퍼 출력 | 일치 |
| DAC_OUT (PA4) | PA04_DAC1_CH0 → 버퍼 입력 | 일치 |
| UART2 (PA2/PA3) | PA02_UART2_TX → ADuM1412 VIA → MAX13488 DI, RO → VIC → PA03_UART2_RX | 일치. 채널 방향 정상 |
| USART1 (PA9/PA10) | PA09_UART1_TX → CH340C RXD, CH340C TXD → PA10_UART1_RX | 일치. 교차 정상 |
| WIZ_CS/SCK/MISO/MOSI | PA15, PC10, PC11, PC12 → WIZ550io A6, A5, A4, A3 | 일치 |
| WIZ_INT/RST/READY | PC7 ← INTn(B5), PC8 → RSTn(B3), PC9 ← RDY(B2) | 일치 |

LED 역할(실크 기준): LED_01 = FAULT(황색), LED_02~03 = RS485/RS232(녹색), LED_04~07 = RELAY 4CH(녹색), LED_08~09 = SPARE(청색). POWER(D2 적색)는 R10을 거쳐 GND에 연결되어 상시 점등됨.

### 8.2 하드웨어 지적 사항

| # | 등급 | 블록 | 내용 | 근거·계산 | 권고 |
|---|---|---|---|---|---|
| H1 | 높음 | RS485 | MAX13488 AutoDirection 사용 중인데 버스 바이어스 R21·R23이 DNP임 | AutoDirection은 DI가 Low→High로 바뀐 뒤 드라이버를 끄고 외부 풀업(A)·풀다운(B)으로 A−B > 200 mV를 유지해야 함. 현재 아이들 A−B ≈ 0 V. 10 kΩ 실장 시에도 5 × 120 / (20,000 + 120) = 29.8 mV로 부족 | R21·R23을 470~560 Ω으로 실장. 목표 250 mV 기준 상한: 종단 1개 1,140 Ω, 양단 종단 570 Ω. 560 Ω일 때 4.2 mA, 저항당 9.9 mW |
| H2 | 높음 | 릴레이 전원 | 더미 부하 R26 110 Ω 0805 정격 초과 | P = 5.0² / 110 = 0.227 W, 0805 일반 정격 0.125 W의 182 % | 2010(0.75 W) 또는 2512(1 W)로 변경 |
| M1 | 중간 | RS485 절연 전원 | U6 B0505LS-1W에 최소 부하가 없음 | 최소 부하 10 % 가정 시 20 mA 필요, 아이들 부하는 10 mA 미만 추정. MAX13488 권장 VCC 4.5~5.5 V [미확인] | 아이들 VISO 측정. 5.5 V 초과 시 더미 부하 약 250 Ω(1206) 추가 또는 안정화형 컨버터로 교체 |
| M2 | 중간 | 릴레이 구동 | 포화 여유 부족 가능 | IF = (3.3 − 1.2) / 1 kΩ = 2.1 mA, Ib = (5.0 − 0.2 − 0.7) / 4.7 kΩ − 0.7 / 47 kΩ = 0.86 mA → 필요 CTR ≥ 41 %. 코일 360 mW(72 mA)면 강제 β 84로 MMBT3904 최소 hFE(50 mA에서 60) 초과 [코일·CTR 미확인] | 4채널 ON 시 Q1~Q4 VCE ≤ 0.3 V 확인. 여유 확보 시 R27/30/33/36 → 470 Ω, R28/31/34/37 → 2.2 kΩ |
| M3 | 중간 | 아날로그 입력 | CN6 입력에 TVS·풀다운 없음 | 24 V 오결선 시 (24 − 5.5) / 1 kΩ ≈ 18 mA가 TLV9001 입력 보호 다이오드로 흐름. 단선 시 입력 부정 | 입력단 TVS와 풀다운(100 kΩ~1 MΩ) 추가 |
| M4 | 중간 | WIZ550io | RDY 대기와 드라이버 고정 대기 불일치 가능 | 6절 #18 참조 | 파형 측정 후 판단 |
| M5 | 중간 | MCU | VCAP_1·VCAP_2 각 4.7 µF | STM32F429 권장값 2.2 µF로 기억함 [미확인] | 데이터시트의 VCAP 조건 확인 |
| L1 | 낮음 | RS485 | 종단 R22 120 Ω 고정 실장 | 버스 중간 노드로 설치 시 종단 과다 | 점퍼 선택형으로 변경 |
| L2 | 낮음 | 부트 | BOOT0이 10 kΩ로 GND 고정, CH340C DTR/RTS 미연결 | ROM 부트로더 진입 불가. 복구는 SWD(CN1)로만 가능 | BOOT0 점퍼 또는 패드 추가 |
| L3 | 낮음 | ADuM1412 | 미사용 입력 VIB(4)·VID(11)와 CTRL1·CTRL2 개방 | 입력 핀 개방은 권장되지 않음 [미확인] | 미사용 입력은 해당 측 GND로 고정 |
| L4 | 낮음 | LED | D4(SPARE, 청색) 전류 약 0.4 mA 추정 | (3.3 − 2.9) / 1 kΩ [VF 미확인] | 밝기 확인 후 저항 조정 |
| L5 | 낮음 | 전원 | LD1117 손실 약 0.46 W 추정 | +3V3 약 270 mA 추정(MCU 100, W5500 132, CH340 12, LED 13, 포토커플러 8 mA 등), (5.0 − 3.3) × 0.27 | 패키지·방열 동박 확인, 최대 부하에서 온도 측정 |

확인된 정상 항목: CH340C 3.3 V 동작 결선(V3 = VCC), USB-C CC 5.1 kΩ, USBLC6, D+/D− 33 Ω, VBAT–VDD 직결(LSI 사용과 일치), VDDA 필터, RS485 보호(TBU-CA065, TISP4240, SM712), 릴레이 플라이백 다이오드 방향, GND/PGND·ISO_GND 절연 구조, AC 입력부(퓨즈 1 A, 바리스터 561, X2 0.22 µF, 공통모드 초크, HLK-10M05). +5V 부하는 약 0.75 A로 추정되어 HLK-10M05(2 A) 대비 여유가 있음.

### 8.3 펌웨어 시험에 미치는 영향

| 지적 | 증상 | 확인 수단 |
|---|---|---|
| H1 | RS485 수신 문자 깨짐, `RtuSlave.crc_errors`·`dropped` 증가 | `tests/hw/test_rs485.py`, `tests/hw/test_modbus.py` 종료 시 RTU 통계 |
| M2 | 릴레이 미동작 또는 접점 채터링 | `tests/hw/test_do.py` 실행 중 VCE 측정 |
| M3 | 입력 미연결 시 IR 값 변동 | `tests/hw/test_ai.py` 입력 개방 상태 출력 |
| M4 | 링크 미확립, MAC 불일치 | `tests/hw/test_eth.py`의 WIZ_READY·MAC 출력 |

