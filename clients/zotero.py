from __future__ import annotations

import os
import re
from typing import Any

from ._http import build_url, json_get, json_post
from ..models import PaperRecord, normalize_doi, normalize_title


DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/\S+\b", re.IGNORECASE)


class ZoteroClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        library_type: str | None = None,
        library_id: str | None = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("ZOTERO_API_KEY", "")).strip()
        self.library_type = (library_type or os.getenv("ZOTERO_LIBRARY_TYPE", "user")).strip()
        self.library_id = (library_id or os.getenv("ZOTERO_LIBRARY_ID", "")).strip()

    def is_configured(self) -> bool:
        return bool(self.api_key and self.library_type and self.library_id)

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Zotero-API-Version": "3",
            "Authorization": f"Bearer {self.api_key}",
        }

    @staticmethod
    def _extract_doi(data: dict[str, Any]) -> str:
        doi = str(data.get("DOI") or "").strip()
        if doi:
            return doi
        extra = str(data.get("extra") or "")
        match = DOI_PATTERN.search(extra)
        return match.group(0).strip() if match else ""

    @staticmethod
    def _extract_year(data: dict[str, Any]) -> int | None:
        date = str(data.get("date") or "").strip()
        if len(date) >= 4 and date[:4].isdigit():
            return int(date[:4])
        return None

    @staticmethod
    def _extract_authors(data: dict[str, Any]) -> list[str]:
        creators = data.get("creators") or []
        if not isinstance(creators, list):
            return []
        authors: list[str] = []
        for creator in creators:
            if not isinstance(creator, dict):
                continue
            if creator.get("creatorType") not in {"author", "editor"}:
                continue
            first = str(creator.get("firstName") or "").strip()
            last = str(creator.get("lastName") or "").strip()
            full = " ".join(v for v in [first, last] if v).strip()
            if not full:
                full = str(creator.get("name") or "").strip()
            if full:
                authors.append(full)
        return authors

    def fetch_collection_seeds(self, collection_key: str, limit: int = 200) -> list[dict[str, Any]]:
        if not self.is_configured() or not collection_key:
            return []
        seeds: list[dict[str, Any]] = []
        per_page = min(max(limit, 1), 100)
        start = 0
        while len(seeds) < limit:
            url = build_url(
                f"https://api.zotero.org/{self.library_type}s/{self.library_id}/collections/{collection_key}/items/top",
                {
                    "include": "data",
                    "itemType": "-attachment",
                    "limit": per_page,
                    "start": start,
                },
            )
            payload = json_get(url, headers=self._headers())
            if not isinstance(payload, list) or not payload:
                break
            for item in payload:
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key") or "").strip()
                data = item.get("data") or {}
                if not isinstance(data, dict):
                    continue
                title = str(data.get("title") or "").strip()
                doi = self._extract_doi(data)
                if not title and not doi:
                    continue
                seeds.append(
                    {
                        "source": "zotero",
                        "source_id": key,
                        "paper_id": key,
                        "title": title,
                        "doi": doi,
                        "year": self._extract_year(data),
                        "authors": self._extract_authors(data),
                        "seed_from": collection_key,
                    }
                )
                if len(seeds) >= limit:
                    break
            if len(payload) < per_page:
                break
            start += per_page
        return seeds

    def _fetch_existing_keys(self, collection_key: str | None, limit: int = 500) -> tuple[set[str], set[str]]:
        if not self.is_configured():
            return set(), set()
        doi_set: set[str] = set()
        title_set: set[str] = set()
        if collection_key:
            base = f"https://api.zotero.org/{self.library_type}s/{self.library_id}/collections/{collection_key}/items/top"
        else:
            base = f"https://api.zotero.org/{self.library_type}s/{self.library_id}/items/top"

        start = 0
        per_page = min(max(limit, 1), 100)
        while len(doi_set) + len(title_set) < limit:
            url = build_url(
                base,
                {
                    "include": "data",
                    "itemType": "-attachment",
                    "limit": per_page,
                    "start": start,
                },
            )
            payload = json_get(url, headers=self._headers())
            if not isinstance(payload, list) or not payload:
                break
            for item in payload:
                if not isinstance(item, dict):
                    continue
                data = item.get("data") or {}
                if not isinstance(data, dict):
                    continue
                doi = normalize_doi(self._extract_doi(data))
                if doi:
                    doi_set.add(doi)
                title = normalize_title(str(data.get("title") or "").strip())
                if title:
                    title_set.add(title)
            if len(payload) < per_page:
                break
            start += per_page
        return doi_set, title_set

    def fetch_existing_signatures(self, collection_key: str | None, limit: int = 1200) -> tuple[set[str], set[str]]:
        return self._fetch_existing_keys(collection_key=collection_key, limit=limit)

    @staticmethod
    def _to_zotero_item(record: PaperRecord, collection_key: str | None) -> dict[str, Any]:
        creators = []
        for author in record.authors:
            name = author.strip()
            if not name:
                continue
            parts = name.split()
            if len(parts) > 1:
                creators.append({"creatorType": "author", "firstName": " ".join(parts[:-1]), "lastName": parts[-1]})
            else:
                creators.append({"creatorType": "author", "name": name})

        item: dict[str, Any] = {
            "itemType": "journalArticle",
            "title": record.title,
            "creators": creators,
            "date": str(record.year) if record.year else "",
            "DOI": record.doi,
            "publicationTitle": record.venue,
            "url": record.url,
            "abstractNote": record.abstract,
            "extra": f"ingested_by: myocean_search\nsource: {record.source}\nsource_id: {record.source_id}",
            "tags": [{"tag": "ingested/search_mvp"}, {"tag": f"retrieval/{record.retrieval_mode}"}],
        }
        if collection_key:
            item["collections"] = [collection_key]
        return item

    def import_candidates(
        self,
        records: list[PaperRecord],
        *,
        collection_key: str | None = None,
        limit: int = 50,
        apply: bool = False,
        skip_existing: bool = True,
    ) -> dict[str, Any]:
        if not self.is_configured():
            return {"status": "missing_zotero_config", "planned": 0, "imported": 0}

        capped = records[: max(0, limit)]
        existing_doi, existing_title = self._fetch_existing_keys(collection_key, limit=1200) if skip_existing else (set(), set())

        payload_items: list[dict[str, Any]] = []
        skipped_existing = 0
        for rec in capped:
            n_doi = normalize_doi(rec.doi)
            n_title = normalize_title(rec.title)
            if skip_existing and ((n_doi and n_doi in existing_doi) or (n_title and n_title in existing_title)):
                skipped_existing += 1
                continue
            payload_items.append(self._to_zotero_item(rec, collection_key))

        if not apply:
            return {
                "status": "dry_run",
                "planned": len(payload_items),
                "imported": 0,
                "skipped_existing": skipped_existing,
                "sample_titles": [item.get("title", "") for item in payload_items[:5]],
            }

        imported = 0
        failed_batches = 0
        batch_size = 50
        post_url = f"https://api.zotero.org/{self.library_type}s/{self.library_id}/items"
        for i in range(0, len(payload_items), batch_size):
            batch = payload_items[i : i + batch_size]
            response = json_post(post_url, batch, headers=self._headers())
            if isinstance(response, dict):
                successful = response.get("successful")
                if isinstance(successful, dict):
                    imported += len(successful)
                else:
                    # fallback: assume success if API returns dict without explicit errors
                    imported += len(batch)
            else:
                failed_batches += 1

        return {
            "status": "applied" if failed_batches == 0 else "partial",
            "planned": len(payload_items),
            "imported": imported,
            "failed_batches": failed_batches,
            "skipped_existing": skipped_existing,
        }
