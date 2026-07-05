"""지역/격자/비용 추정 테스트 (API 키 불필요)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.regions import (  # noqa: E402
    Region,
    build_grid,
    count_grid_points,
    estimate_cost,
    load_regions_csv,
)


def test_count_matches_build_grid():
    r = 0.5
    step = 400
    assert count_grid_points(r, step) == len(build_grid(37.5, 127.0, r, step))


def test_estimate_scales_with_regions():
    one = estimate_cost([Region("a", 37.5, 127.0, 1.0)], 400)
    two = estimate_cost(
        [Region("a", 37.5, 127.0, 1.0), Region("b", 35.1, 129.0, 1.0)], 400
    )
    assert two["grid_cells"] == 2 * one["grid_cells"]
    assert two["google_cost_usd"] > one["google_cost_usd"]


def test_load_starter_regions_file():
    path = Path(__file__).resolve().parent.parent / "data" / "korea_regions.csv"
    regions = load_regions_csv(path)
    assert len(regions) >= 20
    assert all(33 < r.lat < 39 for r in regions)
    assert all(124 < r.lng < 132 for r in regions)


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call(["pytest", "-v", __file__]))
