from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import quote

from ._http import build_url, json_get


class CrossrefClient:
    def __init__(self, *, mailto: str | None = None) -> None:
        self.mailto = mailto
        self.max_lookups = int(os.getenv("ZOTERO_SEARCH_CROSSREF_MAX_LOOKUPS", "60"))
        self.delay_seconds = max(0.0, float(os.getenv("ZOTERO_SEARCH_CROSSREF_DELAY_SECONDS", "0.15")))
        self._cache: dict[str, dict[str, Any] | None] = {}
        self._lookup_count = 0

    def _lookup_by_doi(self, doi: str) -> dict[str, Any] | None:
        if not doi:
            return None
        key = doi.strip().lower()
        if key in self._cache:
            return self._cache[key]
        if self._lookup_count >= self.max_lookups:
            self._cache[key] = None
            return None
        if self._lookup_count > 0 and self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        self._lookup_count += 1
        url = build_url(f"https://api.crossref.org/works/{quote(doi)}", {"mailto": self.mailto})
        payload = json_get(url)
        if not isinstance(payload, dict):
            self._cache[key] = None
            return None
        message = payload.get("message")
        if isinstance(message, dict):
            self._cache[key] = message
            return message
        self._cache[key] = None
        return None

    @staticmethod
    def _pick_title(message: dict[str, Any]) -> str:
        title = message.get("title")
        if isinstance(title, list) and title:
            return str(title[0]).strip()
        if isinstance(title, str):
            return title.strip()
        return ""

    @staticmethod
    def _pick_year(message: dict[str, Any]) -> int | None:
        issued = message.get("issued") or {}
        date_parts = issued.get("date-parts")
        if isinstance(date_parts, list) and date_parts and isinstance(date_parts[0], list) and date_parts[0]:
            year = date_parts[0][0]
            if isinstance(year, int):
                return year
        return None

    @staticmethod
    def _pick_venue(message: dict[str, Any]) -> str:
        container = message.get("container-title")
        if isinstance(container, list) and container:
            return str(container[0]).strip()
        if isinstance(container, str):
            return container.strip()
        return ""

    @staticmethod
    def _pick_authors(message: dict[str, Any]) -> list[str]:
        raw = message.get("author") or []
        if not isinstance(raw, list):
            return []
        authors: list[str] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            given = str(item.get("given") or "").strip()
            family = str(item.get("family") or "").strip()
            full = " ".join(v for v in [given, family] if v).strip()
            if full:
                authors.append(full)
        return authors

    def enrich(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enriched: list[dict[str, Any]] = []
        for record in records:
            row = dict(record)
            base_trace = [str(v).strip() for v in row.get("source_trace", []) if str(v).strip()]
            if not base_trace and str(row.get("source", "")).strip():
                base_trace = [str(row.get("source", "")).strip()]
            row["source_trace"] = base_trace
            row["enriched_by_crossref"] = bool(row.get("enriched_by_crossref", False))
            doi = str(row.get("doi") or "").strip()
            if not doi:
                enriched.append(row)
                continue
            message = self._lookup_by_doi(doi)
            if not message:
                enriched.append(row)
                continue
            if not row.get("title"):
                row["title"] = self._pick_title(message)
            if not row.get("year"):
                row["year"] = self._pick_year(message)
            if not row.get("venue"):
                row["venue"] = self._pick_venue(message)
            if not row.get("authors"):
                row["authors"] = self._pick_authors(message)
            if not row.get("url"):
                row["url"] = str(message.get("URL") or "").strip()
            row["enriched_by_crossref"] = True
            if "crossref" not in row["source_trace"]:
                row["source_trace"].append("crossref")
            enriched.append(row)
        return enriched
