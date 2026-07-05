"""구글맵 ↔ 카카오맵 비교 자동화 — CLI 진입점.

두 가지 실행 모드:
  1) 단일 지점:  --lat --lng --radius-km        (동네 하나 빠르게)
  2) 전국 배치:  --regions-file data/korea_regions.csv  (지역 목록 순회, 재개 가능)

실제 제보 제출은 자동화하지 않는다(카카오 약관/어뷰징 방지).
필수 항목(장소명·위치)이 채워진 후보만 CSV로 저장하고, 등록은 사람이 한다.
"""
from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv

from . import reporter, runner
from .comparator import find_missing_in_kakao
from .google_maps import GoogleMapsClient, Place
from .kakao_maps import KakaoMapsClient
from .regions import Region, build_grid, estimate_cost, load_regions_csv


def dedupe(places: list[Place]) -> list[Place]:
    seen: set[str] = set()
    out: list[Place] = []
    for p in places:
        if p.place_id in seen:
            continue
        seen.add(p.place_id)
        out.append(p)
    return out


def _print_estimate(regions: list[Region], step_m: float) -> None:
    est = estimate_cost(regions, step_m)
    print("─" * 48)
    print("📊 예상 규모 / 비용 (실행 전 추정)")
    print(f"  대상 지역      : {est['regions']}곳")
    print(f"  격자점 총합    : {est['grid_cells']:,}개")
    print(f"  구글 호출      : {est['google_calls']:,}회")
    print(f"  구글 예상 비용 : 약 ${est['google_cost_usd']:,} USD")
    print(f"  카카오 호출    : 약 {est['kakao_calls']:,}회")
    print(f"  카카오 무료쿼터: 약 {est['kakao_free_quota_days']}일치")
    print("─" * 48)
    print("※ 구글 요금은 계정/할인에 따라 다르며 무료 크레딧이 있을 수 있습니다.")
    print("※ 비용이 부담되면 --max-cells / --max-kakao-calls 로 상한을 거세요.")


def run_single(args, google, kakao) -> None:
    grid = build_grid(args.lat, args.lng, args.radius_km, args.grid_step_m)
    print(f"[격자] {len(grid)}개 탐색점 (반경 {args.radius_km}km)")
    all_places: list[Place] = []
    for i, (la, ln) in enumerate(grid, 1):
        all_places.extend(
            google.search_nearby(
                la, ln, radius_m=args.cell_radius_m, included_types=args.types
            )
        )
        print(f"[구글] {i}/{len(grid)} → 누적 {len(all_places)}건")
    unique = dedupe(all_places)
    candidates = find_missing_in_kakao(unique, kakao)
    print(f"[결과] 카카오맵 미등록 후보 {len(candidates)}건")
    csv_path, json_path = reporter.save(candidates)
    print(f"[저장] {csv_path}\n[저장] {json_path}")


def main() -> None:
    load_dotenv()
    p = argparse.ArgumentParser(
        description="구글맵에 있고 카카오맵에 없는 장소 후보 발굴"
    )
    # 지점 모드
    p.add_argument("--lat", type=float, help="단일 지점 모드: 중심 위도")
    p.add_argument("--lng", type=float, help="단일 지점 모드: 중심 경도")
    p.add_argument("--radius-km", type=float, default=0.5, help="지점 반경(km)")
    # 전국 모드
    p.add_argument(
        "--regions-file", help="전국 모드: 지역 목록 CSV (name,lat,lng,radius_km)"
    )
    p.add_argument(
        "--run-name", default="korea", help="전국 모드: 재개용 실행 이름"
    )
    # 공통
    p.add_argument("--grid-step-m", type=float, default=400, help="격자 간격(m)")
    p.add_argument("--cell-radius-m", type=float, default=300, help="격자점 반경(m)")
    p.add_argument(
        "--types",
        nargs="*",
        default=["restaurant", "cafe", "store"],
        help="구글 장소 타입",
    )
    # 예산/안전장치
    p.add_argument("--max-cells", type=int, help="이번 실행 최대 격자 수")
    p.add_argument("--max-kakao-calls", type=int, help="이번 실행 카카오 호출 상한")
    p.add_argument(
        "--estimate", action="store_true", help="비용만 추정하고 종료(호출 안 함)"
    )
    args = p.parse_args()

    # 대상 지역 구성 (추정용)
    if args.regions_file:
        regions = load_regions_csv(args.regions_file)
    elif args.lat is not None and args.lng is not None:
        regions = [Region("single", args.lat, args.lng, args.radius_km)]
    else:
        p.error("--regions-file 또는 (--lat --lng) 중 하나는 필요합니다.")
        return

    if args.estimate:
        _print_estimate(regions, args.grid_step_m)
        return

    google = GoogleMapsClient(os.getenv("GOOGLE_PLACES_API_KEY", ""))
    kakao = KakaoMapsClient(os.getenv("KAKAO_REST_API_KEY", ""))

    if args.regions_file:
        _print_estimate(regions, args.grid_step_m)
        print(f"\n[전국 모드] {len(regions)}개 지역 순회 시작 (run={args.run_name})")
        runner.run(
            regions=regions,
            google=google,
            kakao=kakao,
            run_name=args.run_name,
            grid_step_m=args.grid_step_m,
            cell_radius_m=args.cell_radius_m,
            types=args.types,
            max_cells=args.max_cells,
            max_kakao_calls=args.max_kakao_calls,
        )
    else:
        run_single(args, google, kakao)


if __name__ == "__main__":
    main()
