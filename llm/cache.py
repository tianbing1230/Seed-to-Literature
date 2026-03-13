from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


class MinimalCacheStore:
    """Single-file cache/checkpoint/summary store (minimal-file mode)."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.root_dir / "cache.jsonl"
        self.checkpoint_file = self.root_dir / "checkpoint.json"
        self.summary_file = self.root_dir / "run_summary.json"
        self._index: dict[str, dict[str, Any]] | None = None

    @staticmethod
    def stable_key(payload: dict[str, Any]) -> str:
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def _ensure_index(self) -> None:
        if self._index is not None:
            return
        self._index = {}
        if not self.cache_file.exists():
            return
        for line in self.cache_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = str(row.get("key") or "").strip()
            value = row.get("value")
            if key:
                self._index[key] = value

    def get(self, key: str) -> dict[str, Any] | None:
        self._ensure_index()
        assert self._index is not None
        value = self._index.get(key)
        if isinstance(value, dict):
            return value
        return None

    def put(self, key: str, value: dict[str, Any]) -> None:
        self._ensure_index()
        assert self._index is not None
        self._index[key] = value
        with self.cache_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")

    def write_checkpoint(self, payload: dict[str, Any]) -> None:
        self.checkpoint_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def read_checkpoint(self) -> dict[str, Any] | None:
        if not self.checkpoint_file.exists():
            return None
        try:
            data = json.loads(self.checkpoint_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            return data
        return None

    def write_run_summary(self, payload: dict[str, Any]) -> None:
        self.summary_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

