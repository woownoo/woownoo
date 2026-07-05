"""구글맵 ↔ 카카오맵 비교 자동화 — CLI 진입점.

지정한 지역을 격자(grid)로 훑으며 구글 장소를 수집하고,
각 장소가 카카오맵에 있는지 확인해 "빠진 장소" 후보를 뽑아낸다.
후보는 카카오 신규 장소 등록 폼에 맞춘 CSV/JSON으로 저장되며,
필수 항목(장소명·위치)이 채워진 것만 포함된다.

실제 제보 제출은 자동화하지 않는다(카카오 약관/어뷰징 방지).
사람이 CSV를 보고 직접 등록하는 것을 전제로 한다.
"""
from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from .comparator import find_missing_in_kakao, haversine_m
from .google_maps import GoogleMapsClient, Place
from .kakao_maps import KakaoMapsClient
from . import reporter


def build_grid(
    lat: float, lng: float, radius_km: float, step_m: float
) -> list[tuple[float, float]]:
    """중심 좌표 기준 정사각형 영역을 step_m 간격 격자점으로 나눈다."""
    # 위도 1도 ≈ 111.32km. 경도는 위도에 따라 보정.
    import math

    lat_deg_per_m = 1 / 111_320.0
    lng_deg_per_m = 1 / (111_320.0 * math.cos(math.radians(lat)))

    half = radius_km * 1000
    points: list[tuple[float, float]] = []
    y = -half
    while y <= half:
        x = -half
        while x <= half:
            points.append(
                (lat + y * lat_deg_per_m, lng + x * lng_deg_per_m)
            )
            x += step_m
        y += step_m
    return points


def dedupe(places: list[Place]) -> list[Place]:
    """place_id 및 근접-동일 이름 기준으로 중복 제거."""
    seen_ids: set[str] = set()
    unique: list[Place] = []
    for p in places:
        if p.place_id in seen_ids:
            continue
        seen_ids.add(p.place_id)
        unique.append(p)
    return unique


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="구글맵에 있고 카카오맵에 없는 장소 후보 발굴"
    )
    parser.add_argument("--lat", type=float, required=True, help="중심 위도")
    parser.add_argument("--lng", type=float, required=True, help="중심 경도")
    parser.add_argument(
        "--radius-km", type=float, default=0.5, help="탐색 반경(km), 기본 0.5"
    )
    parser.add_argument(
        "--grid-step-m", type=float, default=400, help="격자 간격(m), 기본 400"
    )
    parser.add_argument(
        "--cell-radius-m", type=float, default=300, help="격자점당 검색 반경(m)"
    )
    parser.add_argument(
        "--types",
        nargs="*",
        default=["restaurant", "cafe", "store"],
        help="구글 장소 타입 (예: restaurant cafe store)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API 호출 없이 격자 구성만 출력",
    )
    args = parser.parse_args()

    grid = build_grid(args.lat, args.lng, args.radius_km, args.grid_step_m)
    print(f"[격자] {len(grid)}개 탐색점 생성 (반경 {args.radius_km}km)")

    if args.dry_run:
        for i, (la, ln) in enumerate(grid[:5]):
            print(f"  #{i}: {la:.6f}, {ln:.6f}")
        if len(grid) > 5:
            print(f"  ... 외 {len(grid) - 5}개")
        return

    google = GoogleMapsClient(os.getenv("GOOGLE_PLACES_API_KEY", ""))
    kakao = KakaoMapsClient(os.getenv("KAKAO_REST_API_KEY", ""))

    # 1) 구글에서 격자 전체의 장소 수집
    all_places: list[Place] = []
    for i, (la, ln) in enumerate(grid, 1):
        found = google.search_nearby(
            la, ln, radius_m=args.cell_radius_m, included_types=args.types
        )
        all_places.extend(found)
        print(f"[구글] {i}/{len(grid)} 격자점 → 누적 {len(all_places)}건")

    unique = dedupe(all_places)
    print(f"[구글] 중복 제거 후 {len(unique)}개 장소")

    # 2) 카카오와 비교해 빠진 장소 후보 추출 (필수 항목 있는 것만)
    candidates = find_missing_in_kakao(unique, kakao, search_radius_m=100)
    print(f"[결과] 카카오맵 미등록 후보 {len(candidates)}건")

    # 3) 저장
    csv_path, json_path = reporter.save(candidates)
    print(f"[저장] {csv_path}")
    print(f"[저장] {json_path}")
    print(
        "\n필수 항목(장소명·위치)이 채워진 후보만 담겨 있습니다.\n"
        "CSV를 열어 카카오맵 앱 '신규 장소 등록'에서 직접 제보하세요."
    )


if __name__ == "__main__":
    main()
