"""전국 단위 탐색을 위한 지역 정의 · 격자 생성 · 비용 추정.

'대한민국 전역'을 한 번에 격자로 훑는 것은 API 비용/쿼터상 비현실적이므로,
지역(시/군/구 등) 단위로 쪼개 순차·재개 실행하는 것을 전제로 한다.
"""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path

# 남한 대략 경계 (제주 포함). bbox 그리드용 참고값.
KOREA_BBOX = {"lat_min": 33.0, "lat_max": 38.65, "lng_min": 124.5, "lng_max": 131.0}

# 구글 Places API (New) Nearby Search 대략 단가 (USD / 1,000회). 요금은 바뀔 수 있음.
GOOGLE_COST_PER_1K = 32.0
# 카카오 로컬 API 무료 일일 쿼터(참고).
KAKAO_DAILY_FREE_QUOTA = 100_000


@dataclass
class Region:
    name: str
    lat: float
    lng: float
    radius_km: float


def load_regions_csv(path: str | Path) -> list[Region]:
    """지역 목록 CSV를 읽는다. 헤더: name,lat,lng,radius_km"""
    regions: list[Region] = []
    with Path(path).open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            regions.append(
                Region(
                    name=row["name"].strip(),
                    lat=float(row["lat"]),
                    lng=float(row["lng"]),
                    radius_km=float(row["radius_km"]),
                )
            )
    return regions


def build_grid(
    lat: float, lng: float, radius_km: float, step_m: float
) -> list[tuple[float, float]]:
    """중심 좌표 기준 정사각형 영역을 step_m 간격 격자점으로 나눈다."""
    lat_deg_per_m = 1 / 111_320.0
    lng_deg_per_m = 1 / (111_320.0 * math.cos(math.radians(lat)))
    half = radius_km * 1000
    points: list[tuple[float, float]] = []
    y = -half
    while y <= half:
        x = -half
        while x <= half:
            points.append((lat + y * lat_deg_per_m, lng + x * lng_deg_per_m))
            x += step_m
        y += step_m
    return points


def count_grid_points(radius_km: float, step_m: float) -> int:
    """실제 좌표 생성 없이 격자점 개수만 계산."""
    n = int((radius_km * 1000 * 2) // step_m) + 1
    return n * n


def estimate_cost(
    regions: list[Region],
    step_m: float,
    kakao_calls_per_cell: float = 8.0,
) -> dict:
    """전체 실행에 필요한 API 호출 수와 대략적인 비용/소요일 추정.

    kakao_calls_per_cell: 격자점당 발견되는 구글 장소 수의 기대값(=카카오 조회 수).
    도심은 높고 외곽은 낮다. 보수적으로 8 정도로 둔다.
    """
    total_cells = sum(count_grid_points(r.radius_km, step_m) for r in regions)
    google_calls = total_cells
    kakao_calls = int(total_cells * kakao_calls_per_cell)
    google_cost_usd = google_calls / 1000 * GOOGLE_COST_PER_1K
    kakao_days = max(1, math.ceil(kakao_calls / KAKAO_DAILY_FREE_QUOTA))
    return {
        "regions": len(regions),
        "grid_cells": total_cells,
        "google_calls": google_calls,
        "kakao_calls": kakao_calls,
        "google_cost_usd": round(google_cost_usd, 2),
        "kakao_free_quota_days": kakao_days,
    }
