"""제보 후보를 CSV / JSON 파일로 저장한다."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from .comparator import Candidate

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"


def save(candidates: list[Candidate], prefix: str = "candidates") -> tuple[Path, Path]:
    """CSV와 JSON 두 형식으로 저장하고 경로를 반환한다."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = [c.to_row() for c in candidates]

    csv_path = OUTPUT_DIR / f"{prefix}_{stamp}.csv"
    json_path = OUTPUT_DIR / f"{prefix}_{stamp}.json"

    if rows:
        with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
    else:
        csv_path.write_text("후보 없음\n", encoding="utf-8-sig")

    json_path.write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return csv_path, json_path
