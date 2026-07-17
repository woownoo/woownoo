"""rclone 를 이용한 구글드라이브 동기화 래퍼.

구글드라이브 인증/전송은 검증된 rclone 에 맡기고, 이 프로젝트는
'언제·어떤 방향으로' 동기화할지만 제어합니다.
"""
from __future__ import annotations

import logging
import subprocess

log = logging.getLogger(__name__)


class DriveError(RuntimeError):
    pass


class Drive:
    def __init__(self, bin: str, source: str) -> None:
        self.bin = bin
        self.source = source  # 예: gdrive:3dprint

    def _run(self, args: list[str]) -> subprocess.CompletedProcess:
        cmd = [self.bin, *args]
        log.debug("실행: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise DriveError(
                f"rclone 실패({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
            )
        return proc

    def has_changes(self, local_dir: str) -> bool:
        """구글드라이브와 로컬 폴더 사이에 차이가 있으면 True."""
        proc = subprocess.run(
            [self.bin, "check", self.source, local_dir, "--one-way"],
            capture_output=True,
            text=True,
        )
        # rclone check: 차이가 없으면 0, 있으면 1(그 외는 진짜 오류)
        if proc.returncode == 0:
            return False
        if proc.returncode == 1:
            return True
        raise DriveError(f"rclone check 오류: {proc.stderr.strip()}")

    def sync_down(self, local_dir: str) -> None:
        """구글드라이브 → 로컬(USB 이미지) 로 미러링."""
        log.info("구글드라이브 → USB 동기화 중...")
        self._run(["sync", self.source, local_dir, "--transfers", "4"])

    def sync_up(self, local_dir: str) -> None:
        """로컬(USB 이미지) → 구글드라이브 로 새 파일 업로드."""
        log.info("USB → 구글드라이브 업로드 중...")
        # 드라이브의 파일을 지우지 않도록 copy 사용(양방향 시 안전)
        self._run(["copy", local_dir, self.source, "--transfers", "4"])
