"""
부산 5개 권역 정의
- 기상청 격자 좌표 (NX, NY)
- 대표 위경도
- 소속 구/군
"""
from typing import Dict

REGION_GRID: Dict[str, Dict] = {
    "haeundae": {
        "nx": 98, "ny": 76,
        "lat": 35.1631, "lng": 129.1635,
        "districts": ["해운대구", "수영구", "동래구"],
    },
    "seomyeon": {
        "nx": 97, "ny": 75,
        "lat": 35.1558, "lng": 129.0592,
        "districts": ["부산진구", "연제구", "남구"],
    },
    "saha": {
        "nx": 96, "ny": 75,
        "lat": 35.1046, "lng": 129.0186,
        "districts": ["사하구", "서구", "중구", "영도구"],
    },
    "gijang": {
        "nx": 100, "ny": 77,
        "lat": 35.2446, "lng": 129.2222,
        "districts": ["기장군"],
    },
    "gangseo": {
        "nx": 95, "ny": 77,
        "lat": 35.2121, "lng": 128.9808,
        "districts": ["강서구", "북구", "사상구"],
    },
}
