"""메인 동기화 루프.

핵심 아이디어: 프린터에 꽂힌 USB(LUN)를 매번 분리하지 않는다.
먼저 프린터를 전혀 건드리지 않는 '그림자 폴더(shadow)'로 구글드라이브를
받아 보고, 실제로 변경이 있을 때만 USB 를 잠깐 분리해 반영한다.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time

from .config import Config
from .drive import Drive
from .gadget import Gadget

log = logging.getLogger(__name__)


class Syncer:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.drive = Drive(cfg.rclone.bin, cfg.rclone.source)
        self.gadget = Gadget(
            cfg.gadget.image, cfg.gadget.lun_file, cfg.gadget.mount_point
        )
        self.shadow = cfg.sync.shadow_dir
        os.makedirs(self.shadow, exist_ok=True)

    def _is_paused(self) -> bool:
        flag = self.cfg.sync.pause_flag
        if flag and os.path.exists(flag):
            log.info("프린트 중 플래그(%s) 감지 → 이번 동기화 건너뜀.", flag)
            return True
        return False

    @staticmethod
    def _mirror(src: str, dst: str) -> None:
        """src 폴더 내용을 dst 에 그대로 반영(삭제 포함)."""
        subprocess.run(
            ["rsync", "-a", "--delete", f"{src.rstrip('/')}/", f"{dst.rstrip('/')}/"],
            check=True,
        )

    def sync_once(self) -> None:
        if self._is_paused():
            return

        if self.cfg.sync.direction == "both":
            self._sync_both()
        else:
            self._sync_down()

    def _sync_down(self) -> None:
        """구글드라이브 → USB (기본). 변경이 있을 때만 프린터를 건드림."""
        # 1) 프린터를 건드리지 않고 그림자 폴더로 받는다.
        if not self.drive.has_changes(self.shadow):
            return
        log.info("드라이브 변경 감지 → USB 반영을 시작합니다.")
        self.drive.sync_down(self.shadow)

        # 2) 변경이 있을 때만 USB(LUN)를 잠깐 분리해 이미지에 반영.
        with self.gadget.editing() as mount:
            self._mirror(self.shadow, mount)

    def _sync_both(self) -> None:
        """양방향. 프린터가 쓴 파일도 올려야 하므로 매 주기 마운트한다."""
        with self.gadget.editing() as mount:
            # 프린터가 새로 쓴 파일을 먼저 드라이브로 올린 뒤 내려받는다.
            self.drive.sync_up(mount)
            self.drive.sync_down(mount)
            # 그림자 폴더도 최신 상태로 맞춰 둔다.
            self._mirror(mount, self.shadow)

    def run(self) -> None:
        log.info(
            "동기화 시작: %s → USB (주기 %d초, 방향 %s)",
            self.cfg.rclone.source,
            self.cfg.sync.interval_seconds,
            self.cfg.sync.direction,
        )
        while True:
            try:
                self.sync_once()
            except Exception as exc:  # noqa: BLE001 - 루프는 계속 살아 있어야 함
                log.error("동기화 오류: %s", exc)
            time.sleep(self.cfg.sync.interval_seconds)
