"""비교 로직 단위 테스트 (API 키 불필요)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.comparator import (  # noqa: E402
    haversine_m,
    normalize_name,
    is_same_place,
    find_missing_in_kakao,
)
from src.google_maps import Place  # noqa: E402


def test_haversine_known_distance():
    # 서울시청 ~ 강남역 약 8.7km
    d = haversine_m(37.5663, 126.9779, 37.4979, 127.0276)
    assert 8000 < d < 9500


def test_normalize_strips_branch_and_spaces():
    assert normalize_name("스타벅스 강남점") == normalize_name("스타벅스강남")
    assert normalize_name("A B-C(1)") == "abc1"


def test_same_place_true_when_close_and_similar():
    g = Place("google", "g1", "스타벅스 강남점", "주소", 37.4979, 127.0276)
    k = Place("kakao", "k1", "스타벅스강남", "주소", 37.4979, 127.0277)
    assert is_same_place(g, k)


def test_same_place_false_when_far():
    g = Place("google", "g1", "스타벅스", "a", 37.4979, 127.0276)
    k = Place("kakao", "k1", "스타벅스", "b", 37.5663, 126.9779)
    assert not is_same_place(g, k)


def test_required_fields_filter():
    ok = Place("google", "g1", "카페", "서울 어딘가", 37.5, 127.0)
    no_name = Place("google", "g2", "", "주소", 37.5, 127.0)
    no_loc = Place("google", "g3", "카페", "", 0.0, 0.0)
    assert ok.has_required_fields
    assert not no_name.has_required_fields
    assert not no_loc.has_required_fields


class _FakeKakao:
    """카카오 API를 흉내내는 스텁 — 항상 매칭 없음."""

    def search_keyword(self, query, lat=None, lng=None, radius_m=500):
        return []


def test_find_missing_excludes_incomplete_and_keeps_valid():
    places = [
        Place("google", "g1", "새로생긴카페", "서울 강남", 37.5, 127.0),
        Place("google", "g2", "", "주소없는이름", 37.5, 127.0),  # 필수 누락
    ]
    result = find_missing_in_kakao(places, _FakeKakao())
    assert len(result) == 1
    assert result[0].place.name == "새로생긴카페"


if __name__ == "__main__":
    import subprocess

    raise SystemExit(subprocess.call(["pytest", "-v", __file__]))
