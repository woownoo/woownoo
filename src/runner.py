"""전국 배치 러너 — 체크포인트/재개 + 결과 누적 저장.

전국 규모는 한 번에 끝낼 수 없으므로:
  - 이미 처리한 격자점은 건너뛴다(재개 가능).
  - 후보가 나올 때마다 CSV에 즉시 append 한다(중단돼도 결과 보존).
  - 예산(격자 수·카카오 호출 수) 상한에 도달하면 멈춘다(무료 쿼터 보호).
"""
from __future__ import annotations

import csv
import json
import signal
from dataclasses import dataclass, field
from pathlib import Path

from .comparator import find_missing_in_kakao
from .google_maps import GoogleMapsClient, Place
from .kakao_maps import KakaoMapsClient
from .regions import Region, build_grid

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


@dataclass
class Progress:
    """재개를 위한 진행 상태."""

    done_cells: set[str] = field(default_factory=set)
    seen_place_ids: set[str] = field(default_factory=set)
    kakao_calls: int = 0
    google_calls: int = 0
    candidate_count: int = 0

    @classmethod
    def load(cls, path: Path) -> "Progress":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            done_cells=set(data.get("done_cells", [])),
            seen_place_ids=set(data.get("seen_place_ids", [])),
            kakao_calls=data.get("kakao_calls", 0),
            google_calls=data.get("google_calls", 0),
            candidate_count=data.get("candidate_count", 0),
        )

    def save(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "done_cells": sorted(self.done_cells),
                    "seen_place_ids": sorted(self.seen_place_ids),
                    "kakao_calls": self.kakao_calls,
                    "google_calls": self.google_calls,
                    "candidate_count": self.candidate_count,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


CSV_FIELDS = [
    "region",
    "장소명(필수)",
    "위치_주소(필수)",
    "위치_위도(필수)",
    "위치_경도(필수)",
    "업종",
    "전화번호",
    "SNS_웹사이트",
    "영업시간",
    "google_place_id",
    "kakao_nearby_count",
    "kakao_check_url",
    "google_maps_url",
]


def _cell_key(lat: float, lng: float) -> str:
    return f"{lat:.5f},{lng:.5f}"


def run(
    regions: list[Region],
    google: GoogleMapsClient,
    kakao: KakaoMapsClient,
    run_name: str,
    grid_step_m: float,
    cell_radius_m: float,
    types: list[str],
    max_cells: int | None = None,
    max_kakao_calls: int | None = None,
) -> Path:
    """지역 목록을 순회하며 카카오 미등록 후보를 누적 저장한다.

    반환: 결과 CSV 경로.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    progress_path = OUTPUT_DIR / f"{run_name}_progress.json"
    csv_path = OUTPUT_DIR / f"{run_name}_candidates.csv"

    progress = Progress.load(progress_path)
    is_new_csv = not csv_path.exists()

    # Ctrl+C 시 진행 상태를 저장하고 종료
    stop = {"flag": False}

    def _handle(signum, frame):
        stop["flag"] = True
        print("\n[중단] 진행 상태 저장 후 종료합니다...")

    signal.signal(signal.SIGINT, _handle)

    csv_file = csv_path.open("a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
    if is_new_csv:
        writer.writeheader()

    processed_this_run = 0
    try:
        for region in regions:
            cells = build_grid(
                region.lat, region.lng, region.radius_km, grid_step_m
            )
            for la, ln in cells:
                if stop["flag"]:
                    break
                key = _cell_key(la, ln)
                if key in progress.done_cells:
                    continue
                if max_cells is not None and processed_this_run >= max_cells:
                    print(f"[예산] 격자 {max_cells}개 처리 상한 도달")
                    stop["flag"] = True
                    break
                if (
                    max_kakao_calls is not None
                    and progress.kakao_calls >= max_kakao_calls
                ):
                    print(f"[예산] 카카오 호출 {max_kakao_calls}회 상한 도달")
                    stop["flag"] = True
                    break

                places = google.search_nearby(
                    la, ln, radius_m=cell_radius_m, included_types=types
                )
                progress.google_calls += 1

                # 이번 실행에서 처음 보는 place만 카카오 대조
                fresh: list[Place] = [
                    p for p in places if p.place_id not in progress.seen_place_ids
                ]
                for p in fresh:
                    progress.seen_place_ids.add(p.place_id)

                candidates = find_missing_in_kakao(fresh, kakao)
                progress.kakao_calls += sum(
                    1 for p in fresh if p.has_required_fields
                )

                for c in candidates:
                    row = c.to_row()
                    row["region"] = region.name
                    writer.writerow({k: row.get(k, "") for k in CSV_FIELDS})
                    progress.candidate_count += 1
                csv_file.flush()

                progress.done_cells.add(key)
                processed_this_run += 1

                if processed_this_run % 20 == 0:
                    progress.save(progress_path)
                    print(
                        f"[{region.name}] 격자 {processed_this_run}개 처리 · "
                        f"누적 후보 {progress.candidate_count}건 · "
                        f"카카오 {progress.kakao_calls}회"
                    )
            if stop["flag"]:
                break
    finally:
        progress.save(progress_path)
        csv_file.close()

    print(
        f"\n[요약] 이번 실행 {processed_this_run}격자 처리 · "
        f"총 후보 {progress.candidate_count}건\n"
        f"[저장] {csv_path}\n"
        f"[재개] 같은 --run-name 으로 다시 실행하면 이어서 진행됩니다."
    )
    return csv_path
