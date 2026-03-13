from __future__ import annotations

from typing import Any
from urllib.parse import quote

from ._http import build_url, json_get


OPENALEX_BASE = "https://api.openalex.org"


class OpenAlexClient:
    def __init__(self, *, mailto: str | None = None) -> None:
        self.mailto = mailto

    def _to_record(self, work: dict[str, Any]) -> dict[str, Any]:
        doi_url = str(work.get("doi") or "").strip()
        doi = doi_url.replace("https://doi.org/", "").replace("http://doi.org/", "").strip()
        authorships = work.get("authorships") or []
        authors: list[str] = []
        for author_item in authorships:
            author = author_item.get("author") or {}
            name = str(author.get("display_name") or "").strip()
            if name:
                authors.append(name)
        year = work.get("publication_year")
        if year is None:
            pub_date = str(work.get("publication_date") or "").strip()
            if len(pub_date) >= 4 and pub_date[:4].isdigit():
                year = int(pub_date[:4])
        venue = ""
        primary_location = work.get("primary_location") or {}
        source = primary_location.get("source") or {}
        if source:
            venue = str(source.get("display_name") or "").strip()
        return {
            "paper_id": str(work.get("id") or "").strip(),
            "title": str(work.get("display_name") or "").strip(),
            "authors": authors,
            "year": year,
            "doi": doi,
            "venue": venue,
            "abstract": self._extract_abstract(work),
            "url": str(work.get("id") or "").strip(),
            "source": "openalex",
            "source_id": str(work.get("id") or "").strip(),
        }

    @staticmethod
    def _extract_abstract(work: dict[str, Any]) -> str:
        inverted = work.get("abstract_inverted_index")
        if not isinstance(inverted, dict) or not inverted:
            return ""
        pairs: list[tuple[int, str]] = []
        for token, positions in inverted.items():
            if not isinstance(positions, list):
                continue
            for pos in positions:
                if isinstance(pos, int):
                    pairs.append((pos, str(token)))
        if not pairs:
            return ""
        pairs.sort(key=lambda p: p[0])
        return " ".join(token for _, token in pairs)

    @staticmethod
    def _year_filter(years: str | None) -> str | None:
        if not years:
            return None
        value = years.strip()
        if "-" in value:
            start, end = value.split("-", 1)
            start = start.strip()
            end = end.strip()
            if start.isdigit() and end.isdigit():
                return f"from_publication_date:{start}-01-01,to_publication_date:{end}-12-31"
        if value.isdigit():
            return f"from_publication_date:{value}-01-01,to_publication_date:{value}-12-31"
        return None

    def search_works(self, query: str, max_results: int, years: str | None = None) -> list[dict[str, Any]]:
        per_page = max(1, min(max_results, 200))
        filters = self._year_filter(years)
        params = {
            "search": query,
            "per-page": per_page,
            "mailto": self.mailto,
        }
        if filters:
            params["filter"] = filters
        url = build_url(f"{OPENALEX_BASE}/works", params)
        payload = json_get(url)
        if not isinstance(payload, dict):
            return []
        results = payload.get("results") or []
        if not isinstance(results, list):
            return []
        return [self._to_record(item) for item in results[:max_results] if isinstance(item, dict)]

    def _lookup_seed_work(self, seed: dict[str, Any]) -> dict[str, Any] | None:
        doi = str(seed.get("doi") or "").strip()
        if doi:
            seed_url = build_url(
                f"{OPENALEX_BASE}/works",
                {"filter": f"doi:{doi.lower()}", "per-page": 1, "mailto": self.mailto},
            )
            payload = json_get(seed_url)
            if isinstance(payload, dict):
                results = payload.get("results") or []
                if isinstance(results, list) and results and isinstance(results[0], dict):
                    return results[0]
        title = str(seed.get("title") or "").strip()
        if title:
            seed_url = build_url(
                f"{OPENALEX_BASE}/works",
                {"search": title, "per-page": 1, "mailto": self.mailto},
            )
            payload = json_get(seed_url)
            if isinstance(payload, dict):
                results = payload.get("results") or []
                if isinstance(results, list) and results and isinstance(results[0], dict):
                    return results[0]
        return None

    def _fetch_work_by_id(self, openalex_id: str) -> dict[str, Any] | None:
        if not openalex_id:
            return None
        id_path = quote(openalex_id, safe=":/")
        url = build_url(f"{OPENALEX_BASE}/works/{id_path}", {"mailto": self.mailto})
        payload = json_get(url)
        if isinstance(payload, dict):
            return payload
        return None

    def _fetch_citing_works(self, seed_id: str, limit: int) -> list[dict[str, Any]]:
        if not seed_id:
            return []
        collected: list[dict[str, Any]] = []
        per_page = max(1, min(limit, 200))
        page = 1
        while len(collected) < limit and page <= 10:
            url = build_url(
                f"{OPENALEX_BASE}/works",
                {
                    "filter": f"cites:{seed_id}",
                    "per-page": per_page,
                    "page": page,
                    "mailto": self.mailto,
                },
            )
            payload = json_get(url)
            if not isinstance(payload, dict):
                break
            results = payload.get("results") or []
            if not isinstance(results, list) or not results:
                break
            for item in results:
                if isinstance(item, dict):
                    collected.append(item)
                    if len(collected) >= limit:
                        break
            page += 1
        return collected[:limit]

    def expand_from_seed(
        self,
        seed: dict[str, Any],
        max_results: int,
        ref_depth: int,
        *,
        ref_ratio: float = 0.5,
        include_cited_by: bool = True,
    ) -> list[dict[str, Any]]:
        _ = ref_depth  # kept for future multi-hop expansion
        seed_work = self._lookup_seed_work(seed)
        if not seed_work:
            return []

        seed_id = str(seed_work.get("id") or "").strip()
        ref_ids = seed_work.get("referenced_works") or []
        ref_ids = [str(v).strip() for v in ref_ids if str(v).strip()]

        clipped_ratio = max(0.0, min(ref_ratio, 1.0))
        ref_limit = int(max_results * clipped_ratio)
        cite_limit = max_results - ref_limit if include_cited_by else 0
        expanded: list[dict[str, Any]] = []

        for ref_id in ref_ids[:ref_limit]:
            ref_work = self._fetch_work_by_id(ref_id)
            if ref_work:
                row = self._to_record(ref_work)
                row["expansion_edge"] = "reference"
                expanded.append(row)

        for cite_work in self._fetch_citing_works(seed_id=seed_id, limit=cite_limit):
            row = self._to_record(cite_work)
            row["expansion_edge"] = "cited_by"
            expanded.append(row)

        return expanded[:max_results]
