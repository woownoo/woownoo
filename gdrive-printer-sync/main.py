#!/usr/bin/env python3
"""구글드라이브 ↔ 3D프린터 USB 동기화 진입점."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from src import config
from src.syncer import Syncer


def main() -> int:
    parser = argparse.ArgumentParser(description="구글드라이브 ↔ 3D프린터 USB 동기화")
    parser.add_argument(
        "-c",
        "--config",
        default=os.path.join(os.path.dirname(__file__), "config.yaml"),
        help="설정 파일 경로 (기본: ./config.yaml)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="한 번만 동기화하고 종료 (테스트용)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="디버그 로그")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = config.load(args.config)
    syncer = Syncer(cfg)

    if args.once:
        syncer.sync_once()
        return 0

    try:
        syncer.run()
    except KeyboardInterrupt:
        logging.info("종료합니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
