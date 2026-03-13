from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .cache import MinimalCacheStore
from .client import LLMClient
from ..models import PaperRecord


SYSTEM_PROMPT = (
    "You are screening papers for collection membership. "
    "Only label unrelated when clearly out of scope. "
    "If uncertain, choose peripheral. "
    "Return strict JSON."
)


def _fingerprint(record: PaperRecord) -> str:
    raw = json.dumps(
        {
            "paper_id": record.paper_id,
            "doi": record.doi,
            "title": record.title,
            "year": record.year,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _make_user_prompt(*, profile: dict[str, Any], candidate: PaperRecord) -> str:
    exemplars = profile.get("exemplars") or []
    lines = [
        "Collection profile:",
        str(profile.get("description") or ""),
        f"Top terms: {', '.join(profile.get('top_terms') or [])}",
        "",
        "Seed exemplars:",
    ]
    for idx, ex in enumerate(exemplars[:2], start=1):
        lines.append(f"{idx}) {ex.get('title', '')}")
        if ex.get("abstract"):
            lines.append(str(ex.get("abstract")))
    lines += [
        "",
        "Candidate paper:",
        f"Title: {candidate.title}",
        f"Abstract: {candidate.abstract}",
        f"Year: {candidate.year}",
        "",
        "Return JSON with keys:",
        "decision (core|peripheral|unrelated),",
        "relevance_score (0-1),",
        "summary (one sentence),",
        "reason (short),",
        "novelty_hint (foundational|methodological|application|adjacent).",
    ]
    return "\n".join(lines)


def apply_llm_triage(
    *,
    records: list[PaperRecord],
    profile: dict[str, Any],
    provider: str,
    model: str,
    cache_dir: Path,
    max_candidates: int,
    batch_size: int,
) -> dict[str, Any]:
    cache = MinimalCacheStore(cache_dir)
    client = LLMClient(provider=provider, model=model)
    usage_summary = {
        "provider": provider,
        "model": model,
        "llm_calls_total": 0,
        "llm_token_prompt_total": 0,
        "llm_token_completion_total": 0,
        "llm_token_total": 0,
        "llm_cache_hit_count": 0,
        "llm_cache_miss_count": 0,
        "llm_error_count": 0,
    }
    if not client.is_configured():
        usage_summary["status"] = "disabled_missing_key_or_model"
        cache.write_run_summary(usage_summary)
        return usage_summary

    subset = records[: max(0, max_candidates)]
    start_index = 0
    checkpoint = cache.read_checkpoint()
    if isinstance(checkpoint, dict):
        cp_total = int(checkpoint.get("total_candidates", 0) or 0)
        cp_idx = int(checkpoint.get("batch_end_index", 0) or 0)
        if cp_total == len(subset) and 0 < cp_idx < len(subset):
            start_index = cp_idx

    for i in range(start_index, len(subset), max(1, batch_size)):
        batch = subset[i : i + max(1, batch_size)]
        for rec in batch:
            cache_key = cache.stable_key(
                {
                    "prompt_version": "v1",
                    "provider": provider,
                    "model": model,
                    "profile_hash": hashlib.sha256(json.dumps(profile, sort_keys=True).encode("utf-8")).hexdigest(),
                    "candidate": _fingerprint(rec),
                }
            )
            cached = cache.get(cache_key)
            if cached:
                usage_summary["llm_cache_hit_count"] += 1
                _apply_triage_fields(rec, cached)
                continue

            usage_summary["llm_cache_miss_count"] += 1
            result = client.chat_json(system_prompt=SYSTEM_PROMPT, user_prompt=_make_user_prompt(profile=profile, candidate=rec))
            if not result.get("ok"):
                usage_summary["llm_error_count"] += 1
                continue
            data = result.get("data") or {}
            usage = result.get("usage") or {}
            usage_summary["llm_calls_total"] += 1
            usage_summary["llm_token_prompt_total"] += int(usage.get("prompt_tokens", 0) or 0)
            usage_summary["llm_token_completion_total"] += int(usage.get("completion_tokens", 0) or 0)
            usage_summary["llm_token_total"] += int(usage.get("total_tokens", 0) or 0)
            cache.put(cache_key, data)
            _apply_triage_fields(rec, data)

        cache.write_checkpoint({"batch_end_index": i + len(batch), "total_candidates": len(subset)})

    usage_summary["status"] = "ok"
    cache.write_run_summary(usage_summary)
    return usage_summary


def _apply_triage_fields(record: PaperRecord, triage: dict[str, Any]) -> None:
    decision = str(triage.get("decision") or "").strip().lower()
    if decision not in {"core", "peripheral", "unrelated"}:
        decision = "peripheral"
    record.llm_decision = decision
    try:
        record.llm_relevance_score = float(triage.get("relevance_score", 0.0) or 0.0)
    except Exception:
        record.llm_relevance_score = 0.0
    record.llm_summary = str(triage.get("summary") or "").strip()
    record.llm_reason = str(triage.get("reason") or "").strip()
    novelty = str(triage.get("novelty_hint") or "").strip().lower()
    if novelty not in {"foundational", "methodological", "application", "adjacent"}:
        novelty = "adjacent"
    record.llm_novelty_hint = novelty
