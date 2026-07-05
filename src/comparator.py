"""구글 장소가 카카오맵에 존재하는지 판정하는 비교 로직.

핵심 아이디어:
  구글에서 찾은 장소 하나하나에 대해, 그 좌표 주변을 카카오맵에서 검색해
  "이름이 비슷하고 거리가 가까운" 장소가 있는지 확인한다.
  없으면 → 카카오맵에 빠진 제보 후보.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from .google_maps import Place
from .kakao_maps import KakaoMapsClient

# 이 거리(m) 안에서 이름이 유사하면 "같은 장소"로 본다.
MATCH_RADIUS_M = 60.0
# 이름 유사도 임계값 (0~100). 이 이상이면 같은 이름으로 본다.
NAME_SIMILARITY_THRESHOLD = 70.0

# 이름 정규화 시 제거할 흔한 접미/브랜치 표현
_BRANCH_PATTERN = re.compile(r"(점|지점|본점|직영점|\d+호점)$")
_NOISE_PATTERN = re.compile(r"[\s\(\)\[\]\-_,.·]")


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """두 좌표 사이 거리(미터)."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def normalize_name(name: str) -> str:
    """공백·기호·지점 표기를 제거해 이름 비교를 안정화한다."""
    n = _NOISE_PATTERN.sub("", name)
    n = _BRANCH_PATTERN.sub("", n)
    return n.lower()


def is_same_place(g: Place, k: Place) -> bool:
    """구글 장소 g 와 카카오 장소 k 가 같은 곳인지 판정."""
    if haversine_m(g.lat, g.lng, k.lat, k.lng) > MATCH_RADIUS_M:
        return False
    gn, kn = normalize_name(g.name), normalize_name(k.name)
    if not gn or not kn:
        return False
    # 부분 포함(한쪽이 다른 쪽에 들어감)도 매칭으로 인정
    score = max(fuzz.ratio(gn, kn), fuzz.partial_ratio(gn, kn))
    return score >= NAME_SIMILARITY_THRESHOLD


@dataclass
class Candidate:
    """카카오맵에 없다고 판정된 구글 장소 (= 제보 후보)."""

    place: Place
    kakao_nearby_count: int  # 주변에서 카카오가 찾은 장소 수 (0이면 신뢰도 ↑)

    def to_row(self) -> dict:
        p = self.place
        return {
            # ── 카카오 신규 장소 등록 필수 항목 ──
            "장소명(필수)": p.name,
            "위치_주소(필수)": p.address,
            "위치_위도(필수)": p.lat,
            "위치_경도(필수)": p.lng,
            # ── 카카오 선택 항목 (있으면 승인율↑) ──
            "업종": p.category,
            "전화번호": p.phone,
            "SNS_웹사이트": p.website,
            "영업시간": p.opening_hours,
            # ── 참고/검증용 ──
            "google_place_id": p.place_id,
            "kakao_nearby_count": self.kakao_nearby_count,
            # 사람이 바로 눌러 확인할 수 있는 카카오맵 검색 링크
            "kakao_check_url": f"https://map.kakao.com/?q={p.name}",
            "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{p.place_id}",
        }


def find_missing_in_kakao(
    google_places: list[Place],
    kakao: KakaoMapsClient,
    search_radius_m: int = 100,
) -> list[Candidate]:
    """구글 장소들 중 카카오맵에서 매칭되지 않는 것들을 후보로 반환."""
    candidates: list[Candidate] = []
    for g in google_places:
        # 카카오 제보에는 장소명·위치가 필수이므로, 이 값이 없는 후보는 제외한다.
        if not g.has_required_fields:
            continue
        # 이름으로 카카오를 검색하되 좌표 반경을 걸어 동명이인(다른 지역)을 배제
        kakao_hits = kakao.search_keyword(
            g.name, lat=g.lat, lng=g.lng, radius_m=search_radius_m
        )
        matched = any(is_same_place(g, k) for k in kakao_hits)
        if not matched:
            candidates.append(
                Candidate(place=g, kakao_nearby_count=len(kakao_hits))
            )
    return candidates
