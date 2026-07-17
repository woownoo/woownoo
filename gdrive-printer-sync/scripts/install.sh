#!/bin/bash
# 의존성 설치 + systemd 서비스 등록
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"

if [[ $EUID -ne 0 ]]; then
  echo "sudo 로 실행하세요: sudo $0" >&2
  exit 1
fi

echo "[*] 시스템 패키지 설치 (rclone, rsync, dosfstools, python3)"
apt-get update
apt-get install -y rclone rsync dosfstools python3 python3-pip python3-yaml

echo "[*] 파이썬 의존성 설치"
pip3 install -r "$HERE/requirements.txt" --break-system-packages || \
  pip3 install -r "$HERE/requirements.txt"

echo "[*] systemd 서비스 등록"
sed "s#__WORKDIR__#${HERE}#g" "$HERE/systemd/gdrive-printer-sync.service" \
  > /etc/systemd/system/gdrive-printer-sync.service
systemctl daemon-reload

echo ""
echo "[완료] 다음 순서로 마무리하세요:"
echo "  1) rclone config              # 구글드라이브 remote 생성 (이름: gdrive)"
echo "  2) cp config.example.yaml config.yaml  # 값 채우기"
echo "  3) sudo ./scripts/setup_gadget.sh      # USB gadget 활성화"
echo "  4) sudo systemctl enable --now gdrive-printer-sync"
