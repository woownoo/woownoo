"""구글 Places API (New) 클라이언트.

지정한 좌표 주변의 장소를 카테고리별로 수집한다.
공식 API만 사용하며 웹 스크래핑은 하지 않는다.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import requests

SEARCH_NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"

# 응답에서 받아올 필드. 필요한 것만 요청해야 과금이 줄어든다.
# 카카오 제보 폼의 필수(장소명·위치) + 선택(업종·전화·영업시간·웹) 항목을 모두 채우기 위한 구성.
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",        # 장소명 (필수)
        "places.formattedAddress",   # 위치/주소 (필수)
        "places.location",           # 좌표 (필수)
        "places.primaryTypeDisplayName",  # 업종 (선택)
        "places.primaryType",
        "places.types",
        "places.nationalPhoneNumber",     # 전화번호 (선택)
        "places.websiteUri",              # SNS/웹사이트 (선택)
        "places.regularOpeningHours",     # 영업시간 (선택)
        "places.businessStatus",
    ]
)


@dataclass
class Place:
    """지도 서비스에 독립적인 공통 장소 표현."""

    source: str          # "google" 또는 "kakao"
    place_id: str
    name: str            # 카카오 필수: 장소명
    address: str         # 카카오 필수: 위치
    lat: float           # 카카오 필수: 위치(좌표)
    lng: float           # 카카오 필수: 위치(좌표)
    category: str = ""       # 카카오 선택: 업종
    phone: str = ""          # 카카오 선택: 전화번호
    website: str = ""        # 카카오 선택: SNS
    opening_hours: str = ""  # 카카오 선택: 영업시간
    business_status: str = ""

    @property
    def key(self) -> str:
        return f"{self.source}:{self.place_id}"

    @property
    def has_required_fields(self) -> bool:
        """카카오 신규 장소 등록의 필수 항목(장소명·위치)이 모두 채워졌는지."""
        has_name = bool(self.name and self.name.strip())
        has_location = bool(self.address and self.address.strip()) and (
            self.lat != 0.0 or self.lng != 0.0
        )
        return has_name and has_location


class GoogleMapsClient:
    def __init__(self, api_key: str, language: str = "ko", region: str = "KR"):
        if not api_key:
            raise ValueError("GOOGLE_PLACES_API_KEY 가 설정되지 않았습니다.")
        self.api_key = api_key
        self.language = language
        self.region = region
        self._session = requests.Session()

    def search_nearby(
        self,
        lat: float,
        lng: float,
        radius_m: float = 500.0,
        included_types: list[str] | None = None,
        max_results: int = 20,
    ) -> list[Place]:
        """주어진 좌표 반경 안의 장소를 반환한다.

        radius_m 최대 50000, max_results 최대 20 (구글 제한).
        """
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }
        body: dict = {
            "maxResultCount": min(max_results, 20),
            "languageCode": self.language,
            "regionCode": self.region,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": min(radius_m, 50000.0),
                }
            },
        }
        if included_types:
            body["includedTypes"] = included_types

        resp = self._request(headers, body)
        places: list[Place] = []
        for item in resp.get("places", []):
            loc = item.get("location", {})
            hours = item.get("regularOpeningHours", {})
            weekday_text = hours.get("weekdayDescriptions", []) if hours else []
            category = (
                item.get("primaryTypeDisplayName", {}).get("text", "")
                or item.get("primaryType", "")
            )
            places.append(
                Place(
                    source="google",
                    place_id=item.get("id", ""),
                    name=item.get("displayName", {}).get("text", ""),
                    address=item.get("formattedAddress", ""),
                    lat=loc.get("latitude", 0.0),
                    lng=loc.get("longitude", 0.0),
                    category=category,
                    phone=item.get("nationalPhoneNumber", ""),
                    website=item.get("websiteUri", ""),
                    opening_hours=" / ".join(weekday_text),
                    business_status=item.get("businessStatus", ""),
                )
            )
        return places

    def _request(self, headers: dict, body: dict, retries: int = 3) -> dict:
        for attempt in range(retries):
            resp = self._session.post(
                SEARCH_NEARBY_URL, headers=headers, json=body, timeout=15
            )
            if resp.status_code == 200:
                return resp.json()
            # 쿼터 초과 등 일시적 오류는 백오프 후 재시도
            if resp.status_code in (429, 500, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(
                f"구글 API 오류 {resp.status_code}: {resp.text[:300]}"
            )
        raise RuntimeError("구글 API 재시도 초과")
