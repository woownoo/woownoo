#!/bin/bash
# ─────────────────────────────────────────────────────────────
#  라즈베리파이를 USB 대용량저장장치(USB drive)로 만드는 스크립트
#
#  실행하면:
#    1. 프린터에 노출될 FAT32 디스크 이미지를 만들고
#    2. configfs 로 USB gadget(mass_storage)을 구성한다.
#
#  대상: Raspberry Pi Zero / Zero 2 W / 4 등 USB OTG 지원 보드
#  주의: sudo 로 실행해야 합니다.  sudo ./setup_gadget.sh
# ─────────────────────────────────────────────────────────────
set -euo pipefail

IMG="${IMG:-/home/pi/printer.img}"
SIZE_MB="${SIZE_MB:-2048}"        # USB 용량(MB). 기본 2GB
GADGET="/sys/kernel/config/usb_gadget/g1"

if [[ $EUID -ne 0 ]]; then
  echo "sudo 로 실행하세요: sudo $0" >&2
  exit 1
fi

# ── 1. dwc2 OTG 드라이버 활성화 (재부팅 필요할 수 있음) ──────────
CONFIG_TXT="/boot/firmware/config.txt"
[[ -f "$CONFIG_TXT" ]] || CONFIG_TXT="/boot/config.txt"
if ! grep -q "^dtoverlay=dwc2" "$CONFIG_TXT"; then
  echo "dtoverlay=dwc2" >> "$CONFIG_TXT"
  echo "[안내] $CONFIG_TXT 에 dwc2 를 추가했습니다. 한 번 재부팅 후 다시 실행하세요."
fi
modprobe libcomposite

# ── 2. 프린터에 보일 FAT32 이미지 생성 ─────────────────────────
if [[ ! -f "$IMG" ]]; then
  echo "[*] ${SIZE_MB}MB 디스크 이미지 생성: $IMG"
  dd if=/dev/zero of="$IMG" bs=1M count="$SIZE_MB" status=progress
  mkfs.vfat -F 32 "$IMG"
fi

# ── 3. USB gadget 구성 (configfs) ─────────────────────────────
if [[ -d "$GADGET" ]]; then
  echo "[*] 기존 gadget 제거"
  echo "" > "$GADGET/UDC" 2>/dev/null || true
  rm -rf "$GADGET"
fi

mkdir -p "$GADGET"
cd "$GADGET"
echo 0x1d6b > idVendor          # Linux Foundation
echo 0x0104 > idProduct         # Multifunction Composite Gadget
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "woownoo"          > strings/0x409/manufacturer
echo "GDrive Printer USB" > strings/0x409/product
echo "0001"             > strings/0x409/serialnumber

mkdir -p configs/c.1/strings/0x409
echo "Mass Storage" > configs/c.1/strings/0x409/configuration
echo 250 > configs/c.1/MaxPower

mkdir -p functions/mass_storage.0
echo 1 > functions/mass_storage.0/stall
echo 0 > functions/mass_storage.0/lun.0/cdrom
echo 0 > functions/mass_storage.0/lun.0/ro
echo 0 > functions/mass_storage.0/lun.0/nofua
echo "$IMG" > functions/mass_storage.0/lun.0/file

ln -s functions/mass_storage.0 configs/c.1/

# ── 4. UDC 에 바인딩해 활성화 ──────────────────────────────────
UDC_DEV="$(ls /sys/class/udc | head -n1)"
echo "$UDC_DEV" > UDC

echo ""
echo "[완료] USB gadget 활성화됨 (UDC=$UDC_DEV)"
echo "       LUN 파일: $GADGET/functions/mass_storage.0/lun.0/file"
echo "       config.yaml 의 gadget.lun_file 값을 위 경로로 맞춰 주세요."
