"""카카오 로컬(Local) REST API 클라이언트.

키워드/카테고리 검색으로 특정 좌표 주변의 장소를 조회한다.
비교 시 "카카오에 해당 장소가 존재하는가?"를 판단하는 용도로 쓴다.
"""
from __future__ import annotations

import time

import requests

from .google_maps import Place

KEYWORD_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
CATEGORY_URL = "https://dapi.kakao.com/v2/local/search/category.json"


class KakaoMapsClient:
    def __init__(self, rest_api_key: str):
        if not rest_api_key:
            raise ValueError("KAKAO_REST_API_KEY 가 설정되지 않았습니다.")
        self._headers = {"Authorization": f"KakaoAK {rest_api_key}"}
        self._session = requests.Session()

    def search_keyword(
        self,
        query: str,
        lat: float | None = None,
        lng: float | None = None,
        radius_m: int = 500,
        size: int = 15,
    ) -> list[Place]:
        """키워드로 장소를 검색한다. 좌표를 주면 해당 반경 안에서만 찾는다."""
        params: dict = {"query": query, "size": min(size, 15)}
        if lat is not None and lng is not None:
            # 카카오는 x=경도, y=위도
            params.update({"x": lng, "y": lat, "radius": min(radius_m, 20000)})

        data = self._request(KEYWORD_URL, params)
        return self._parse(data)

    def _parse(self, data: dict) -> list[Place]:
        places: list[Place] = []
        for doc in data.get("documents", []):
            places.append(
                Place(
                    source="kakao",
                    place_id=doc.get("id", ""),
                    name=doc.get("place_name", ""),
                    address=doc.get("road_address_name")
                    or doc.get("address_name", ""),
                    lat=float(doc.get("y", 0.0)),
                    lng=float(doc.get("x", 0.0)),
                    category=doc.get("category_group_name", ""),
                )
            )
        return places

    def _request(self, url: str, params: dict, retries: int = 3) -> dict:
        for attempt in range(retries):
            resp = self._session.get(
                url, headers=self._headers, params=params, timeout=15
            )
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"카카오 API 오류 {resp.status_code}: {resp.text[:300]}"
            )
        raise RuntimeError("카카오 API 재시도 초과")
