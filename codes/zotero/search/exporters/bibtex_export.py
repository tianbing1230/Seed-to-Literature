from __future__ import annotations

from pathlib import Path
import re
from typing import Iterable

from ..models import PaperRecord


def _safe_key(text: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9]+", "", text)[:40]
    return key or "untitled"


def _escape(text: str) -> str:
    return (text or "").replace("{", "\\{").replace("}", "\\}")


def export_bibtex(records: Iterable[PaperRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for idx, rec in enumerate(records, start=1):
            year = rec.year or "0000"
            key_base = rec.doi or rec.title
            citekey = f"{_safe_key(key_base)}{idx}"
            authors = " and ".join(rec.authors)
            f.write(f"@article{{{citekey},\n")
            f.write(f"  title = {{{_escape(rec.title)}}},\n")
            if authors:
                f.write(f"  author = {{{_escape(authors)}}},\n")
            if rec.venue:
                f.write(f"  journal = {{{_escape(rec.venue)}}},\n")
            f.write(f"  year = {{{year}}},\n")
            if rec.doi:
                f.write(f"  doi = {{{_escape(rec.doi)}}},\n")
            if rec.url:
                f.write(f"  url = {{{_escape(rec.url)}}},\n")
            f.write("}\n\n")

