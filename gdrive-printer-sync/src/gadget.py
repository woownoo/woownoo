"""USB 대용량저장장치(gadget) 백킹 이미지 제어.

프린터와 라즈베리파이가 같은 FAT 이미지에 동시에 접근하면 파일시스템이
깨집니다. 그래서 파일을 수정할 때는 반드시 다음 순서를 지킵니다.

    1. detach()  : LUN 파일을 비워 프린터 쪽에서 '드라이브 꺼짐(eject)'으로 인식
    2. mount()   : 파이에서 이미지를 loop 마운트해 읽기/쓰기
    3. (파일 동기화)
    4. unmount() : 마운트 해제
    5. attach()  : LUN 파일을 다시 채워 프린터가 새 내용을 다시 읽음

editing() 컨텍스트 매니저가 이 순서를 안전하게 감싸 줍니다.
"""
from __future__ import annotations

import logging
import subprocess
import time
from contextlib import contextmanager

log = logging.getLogger(__name__)


class GadgetError(RuntimeError):
    pass


def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    log.debug("실행: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GadgetError(
            f"명령 실패({proc.returncode}): {' '.join(cmd)}\n{proc.stderr.strip()}"
        )
    return proc


class Gadget:
    def __init__(self, image: str, lun_file: str, mount_point: str) -> None:
        self.image = image
        self.lun_file = lun_file
        self.mount_point = mount_point
        self._loop_dev: str | None = None

    # ── LUN(프린터에 보이는 드라이브) 연결/해제 ──────────────────
    def attach(self) -> None:
        """이미지를 LUN 에 연결 → 프린터가 드라이브를 인식."""
        with open(self.lun_file, "w") as fh:
            fh.write(self.image)
        log.info("LUN 연결됨 → 프린터가 드라이브를 다시 읽습니다.")

    def detach(self) -> None:
        """LUN 을 비움 → 프린터가 드라이브 꺼짐으로 인식."""
        with open(self.lun_file, "w") as fh:
            fh.write("")
        log.info("LUN 분리됨 → 파이에서 안전하게 이미지 수정 가능.")
        # 프린터 쪽 캐시가 정리될 여유를 줍니다.
        time.sleep(1)

    # ── 파이 쪽 loop 마운트 ─────────────────────────────────────
    def mount(self) -> str:
        proc = _run(["losetup", "--show", "-f", self.image])
        self._loop_dev = proc.stdout.strip()
        _run(["mkdir", "-p", self.mount_point])
        _run(["mount", self._loop_dev, self.mount_point])
        log.info("이미지 마운트: %s → %s", self._loop_dev, self.mount_point)
        return self.mount_point

    def unmount(self) -> None:
        _run(["sync"])
        _run(["umount", self.mount_point], check=False)
        if self._loop_dev:
            _run(["losetup", "-d", self._loop_dev], check=False)
            self._loop_dev = None
        log.info("이미지 마운트 해제 완료.")

    @contextmanager
    def editing(self):
        """detach → mount → (수정) → unmount → attach 를 안전하게 감쌈."""
        self.detach()
        try:
            self.mount()
            yield self.mount_point
        finally:
            self.unmount()
            self.attach()
