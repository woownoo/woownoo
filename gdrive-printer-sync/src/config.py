"""설정(config.yaml) 로딩."""
from __future__ import annotations

import os
from dataclasses import dataclass

import yaml


@dataclass
class RcloneCfg:
    remote: str
    folder: str
    bin: str = "rclone"

    @property
    def source(self) -> str:
        """rclone 원격 경로 (예: gdrive:3dprint)."""
        folder = self.folder.strip("/")
        return f"{self.remote}:{folder}" if folder else f"{self.remote}:"


@dataclass
class GadgetCfg:
    image: str
    lun_file: str
    mount_point: str


@dataclass
class SyncCfg:
    interval_seconds: int = 30
    direction: str = "down"  # "down" 또는 "both"
    pause_flag: str = ""
    # 프린터를 건드리지 않고 드라이브 내용을 먼저 받아두는 로컬 폴더.
    # 여기서 변화를 감지했을 때만 USB(LUN)를 잠깐 분리합니다.
    shadow_dir: str = "/home/pi/gdrive-shadow"


@dataclass
class Config:
    rclone: RcloneCfg
    gadget: GadgetCfg
    sync: SyncCfg


def load(path: str) -> Config:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"설정 파일을 찾을 수 없습니다: {path}\n"
            "config.example.yaml 을 config.yaml 로 복사해서 값을 채워 주세요."
        )
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return Config(
        rclone=RcloneCfg(**raw.get("rclone", {})),
        gadget=GadgetCfg(**raw.get("gadget", {})),
        sync=SyncCfg(**raw.get("sync", {})),
    )
