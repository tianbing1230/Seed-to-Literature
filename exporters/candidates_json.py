from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..models import PaperRecord


def export_jsonl(records: Iterable[PaperRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

