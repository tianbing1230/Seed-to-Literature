from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote

from ._http import build_url, json_get


S2_BASE = "https://api.semanticscholar.org/graph/v1"


class SemanticScholarClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip() or os.getenv("S2_API_KEY", "").strip()

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            return {}
        return {"x-api-key": self.api_key}

    @staticmethod
    def _to_record(paper: dict[str, Any]) -> dict[str, Any]:
        external_ids = paper.get("externalIds") or {}
        doi = str(external_ids.get("DOI") or "").strip()
        authors_raw = paper.get("authors") or []
        authors: list[str] = []
        for author in authors_raw:
            name = str((author or {}).get("name") or "").strip()
            if name:
                authors.append(name)
        return {
            "paper_id": str(paper.get("paperId") or "").strip(),
            "title": str(paper.get("title") or "").strip(),
            "authors": authors,
            "year": paper.get("year"),
            "doi": doi,
            "venue": str(paper.get("venue") or "").strip(),
            "abstract": str(paper.get("abstract") or "").strip(),
            "url": str(paper.get("url") or "").strip(),
            "source": "semanticscholar",
            "source_id": str(paper.get("paperId") or "").strip(),
        }

    def search_works(self, query: str, max_results: int) -> list[dict[str, Any]]:
        url = build_url(
            f"{S2_BASE}/paper/search",
            {
                "query": query,
                "limit": max(1, min(max_results, 100)),
                "fields": "paperId,title,authors,year,abstract,venue,url,externalIds",
            },
        )
        payload = json_get(url, headers=self._headers())
        if not isinstance(payload, dict):
            return []
        data = payload.get("data") or []
        if not isinstance(data, list):
            return []
        return [self._to_record(item) for item in data if isinstance(item, dict)]

    def _lookup_seed_paper_id(self, seed: dict[str, Any]) -> str:
        doi = str(seed.get("doi") or "").strip()
        if doi:
            url = build_url(
                f"{S2_BASE}/paper/DOI:{quote(doi)}",
                {"fields": "paperId"},
            )
            payload = json_get(url, headers=self._headers())
            if isinstance(payload, dict):
                pid = str(payload.get("paperId") or "").strip()
                if pid:
                    return pid
        title = str(seed.get("title") or "").strip()
        if title:
            candidates = self.search_works(query=title, max_results=1)
            if candidates:
                return str(candidates[0].get("paper_id") or "").strip()
        return ""

    def _fetch_edges(
        self,
        paper_id: str,
        *,
        edge: str,
        item_key: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        url = build_url(
            f"{S2_BASE}/paper/{paper_id}/{edge}",
            {
                "limit": max(1, min(limit, 100)),
                "fields": f"{item_key}.paperId,{item_key}.title,{item_key}.authors,{item_key}.year,{item_key}.abstract,{item_key}.venue,{item_key}.url,{item_key}.externalIds",
            },
        )
        payload = json_get(url, headers=self._headers())
        if not isinstance(payload, dict):
            return []
        data = payload.get("data") or []
        if not isinstance(data, list):
            return []
        out: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            paper = item.get(item_key)
            if not isinstance(paper, dict):
                continue
            row = self._to_record(paper)
            row["expansion_edge"] = f"s2_{edge[:-1] if edge.endswith('s') else edge}"
            out.append(row)
        return out

    def expand_from_seed(self, seed: dict[str, Any], max_results: int, *, include_cited_by: bool = True) -> list[dict[str, Any]]:
        paper_id = self._lookup_seed_paper_id(seed)
        if not paper_id:
            return []
        ref_limit = max_results // 2 if include_cited_by else max_results
        cite_limit = max_results - ref_limit if include_cited_by else 0
        results = self._fetch_edges(paper_id, edge="references", item_key="citedPaper", limit=ref_limit)
        if include_cited_by and cite_limit > 0:
            results.extend(self._fetch_edges(paper_id, edge="citations", item_key="citingPaper", limit=cite_limit))
        return results[:max_results]
