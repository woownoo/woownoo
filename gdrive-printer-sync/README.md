# 🖨️ GDrive Printer USB — 구글드라이브 연동 3D프린터 USB

3D프린터 USB 포트에 꽂아두면 **구글드라이브에 올린 G-code가 자동으로 프린터에 나타나는** 장치를 만드는 프로젝트입니다.
SD카드를 뽑아서 PC에 꽂고 다시 프린터에 꽂는 과정을 없애 줍니다.

```
   [PC에서 슬라이싱]                    [3D프린터]
        │                                  ▲
        ▼ 업로드                    USB 드라이브로 인식
   ☁️  구글드라이브  ◀── WiFi ──▶  🥧 라즈베리파이 Zero ──USB──┘
                                    (USB gadget = 가짜 USB 메모리)
```

## 💡 동작 원리

라즈베리파이 Zero는 USB OTG 기능이 있어서, 프린터 입장에서는 **그냥 USB 메모리**로 보이게 만들 수 있습니다(USB Mass Storage Gadget).
파이는 뒤에서 WiFi로 구글드라이브를 감시하다가, 새 파일이 생기면 그 "가짜 USB 메모리"의 내용을 몰래 바꿔치기합니다.

> ⚠️ **SD카드 슬롯이 아니라 USB 포트에 꽂는 방식입니다.** 파이가 SD카드를 흉내낼 수는 없어서, 프린터의 USB-A 포트를 사용하는 기종에 적합합니다. (대부분의 최신 FDM 프린터가 USB 스틱을 지원합니다.)

### 핵심: 동시 접근 방지
프린터와 파이가 같은 FAT 파일시스템에 동시에 쓰면 데이터가 깨집니다. 그래서 파일을 바꿀 때는 이 순서를 지킵니다.

1. **LUN 분리** — 프린터에는 "USB 뽑힘"으로 보이게 함
2. 파이에서 이미지를 마운트해 파일 교체
3. **LUN 재연결** — 프린터가 새 내용을 다시 읽음

또한 프린터를 최대한 안 건드리려고, 먼저 **그림자 폴더(shadow)**로 드라이브를 받아 보고 **실제 변경이 있을 때만** 위 과정을 실행합니다.

## 🛒 준비물

| 항목 | 추천 |
|------|------|
| 보드 | Raspberry Pi Zero 2 W (또는 Zero W) — USB OTG 필수 |
| SD카드 | 파이 OS용 8GB+ |
| USB 케이블 | 파이의 **USB(데이터) 포트** ↔ 프린터 USB-A. 전원 전용 케이블 X |
| 프린터 | USB 스틱을 읽는 FDM 프린터 |

> Zero의 두 USB 중 안쪽(`USB`)이 데이터용입니다. 바깥쪽(`PWR`)은 전원 전용이라 gadget이 동작하지 않습니다.

## 🚀 설치

라즈베리파이(Raspberry Pi OS Lite 권장)에서:

```bash
git clone <이 저장소> && cd gdrive-printer-sync

# 1) 의존성 + systemd 서비스 설치
sudo ./scripts/install.sh

# 2) 구글드라이브 인증 (rclone). remote 이름은 'gdrive' 로
rclone config
#   - n) New remote → 이름: gdrive → 종류: drive(구글 드라이브)
#   - 헤드리스 환경이면 다른 PC에서 rclone authorize 후 토큰 붙여넣기

# 3) 설정 파일 작성
cp config.example.yaml config.yaml
nano config.yaml          # folder, 경로 등 확인

# 4) USB gadget 활성화 (프린터에 USB로 보이게)
sudo ./scripts/setup_gadget.sh
#   dwc2 를 새로 추가했다는 안내가 나오면 sudo reboot 후 다시 실행

# 5) 서비스 시작
sudo systemctl enable --now gdrive-printer-sync
sudo journalctl -u gdrive-printer-sync -f    # 로그 확인
```

## ⚙️ 설정 (`config.yaml`)

`config.example.yaml` 을 참고하세요. 주요 항목:

| 키 | 설명 |
|----|------|
| `rclone.remote` | `rclone config` 에서 만든 이름 (예: `gdrive`) |
| `rclone.folder` | 동기화할 드라이브 폴더 (예: `3dprint`) |
| `gadget.image` | 프린터에 USB로 노출되는 이미지 파일 |
| `gadget.lun_file` | `setup_gadget.sh` 가 알려주는 LUN 경로 |
| `sync.interval_seconds` | 확인 주기(초) |
| `sync.direction` | `down`(드라이브→USB, 기본) / `both`(양방향) |
| `sync.pause_flag` | 이 파일이 있으면 그 주기 동기화를 건너뜀 |
| `sync.shadow_dir` | 프린터를 안 건드리고 먼저 받아두는 폴더 |

## 🧪 테스트

한 번만 동기화해 보고 싶다면:

```bash
sudo python3 main.py --config config.yaml --once -v
```

## 🖨️ 프린트 중 동기화 방지 (권장)

프린트 도중 USB가 분리되면 출력이 끊길 수 있습니다. 프린트를 시작할 때
`sync.pause_flag` 로 지정한 파일을 만들고, 끝나면 지우면 그 사이에는 동기화가 멈춥니다.

- **OctoPrint** 사용 시: 이벤트 훅으로 `PrintStarted` → `touch ~/.printing`, `PrintDone`/`PrintFailed` → `rm ~/.printing`
- **Klipper/Moonraker** 사용 시: 매크로에서 같은 방식으로 플래그 파일 제어

## 🧯 문제 해결

| 증상 | 확인 |
|------|------|
| 프린터가 USB를 못 봄 | 데이터용 USB 포트인지, `setup_gadget.sh` 재실행, dwc2 재부팅 여부 |
| `rclone` 인증 오류 | `rclone lsd gdrive:` 로 접근 확인 |
| 파일이 안 바뀜 | `journalctl -u gdrive-printer-sync -f` 로 "변경 감지" 로그 확인 |
| FAT 손상 경고 | 프린트 중 동기화가 겹쳤을 가능성 → `pause_flag` 설정 |

## 📁 구조

```
gdrive-printer-sync/
├── main.py                     진입점 (동기화 루프 실행)
├── config.example.yaml         설정 예시
├── src/
│   ├── config.py               설정 로딩
│   ├── gadget.py               USB gadget(LUN)·이미지 마운트 제어
│   ├── drive.py                rclone 구글드라이브 래퍼
│   └── syncer.py               그림자 폴더 기반 동기화 로직
├── scripts/
│   ├── setup_gadget.sh         USB gadget 구성
│   └── install.sh              의존성·서비스 설치
└── systemd/
    └── gdrive-printer-sync.service
```

## ⚠️ 한계 / 참고
- 프린터가 **USB 스틱**을 지원해야 합니다(SD 전용 기종은 불가).
- 프린터가 파일 목록을 캐싱하면 새로고침을 위해 메뉴에서 USB를 다시 선택해야 할 수 있습니다.
- 대용량 파일은 WiFi 속도에 따라 반영이 지연됩니다.
