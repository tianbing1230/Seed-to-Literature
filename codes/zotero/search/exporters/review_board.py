from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from ..models import PaperRecord


def export_review_board(records: Iterable[PaperRecord], output_path: Path, title: str = "Candidate Review Board") -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "paper_id": r.paper_id,
            "title": r.title,
            "authors": ", ".join(r.authors),
            "year": r.year,
            "doi": r.doi,
            "source_trace": ", ".join(r.source_trace),
            "rank_score_raw": r.rank_score_raw,
            "rank_score_final": r.rank_score_final,
            "llm_decision": r.llm_decision,
            "llm_relevance_score": r.llm_relevance_score,
            "llm_summary": r.llm_summary,
            "llm_reason": r.llm_reason,
            "llm_novelty_hint": r.llm_novelty_hint,
            "eval_status": r.eval_status,
            "eval_notes": r.eval_notes,
            "url": r.url,
        }
        for r in records
    ]
    data_json = json.dumps(payload, ensure_ascii=False)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 20px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; vertical-align: top; }}
    th {{ background: #f5f7fa; position: sticky; top: 0; }}
    input[type='text'] {{ width: 100%; box-sizing: border-box; }}
    .title {{ max-width: 460px; }}
    .meta {{ color: #666; font-size: 12px; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  <p class="meta">Evaluation is saved to browser localStorage only. CSV remains unchanged unless you sync manually.</p>
  <table>
    <thead>
      <tr>
        <th>#</th><th>Title</th><th>Year</th><th>Rank Raw</th><th>Rank Final</th><th>LLM</th><th>LLM Summary</th><th>Sources</th><th>Eval</th><th>Notes</th>
      </tr>
    </thead>
    <tbody id="rows"></tbody>
  </table>
  <script>
    const data = {data_json};
    const key = "zotero_search_eval_" + location.pathname;
    const saved = JSON.parse(localStorage.getItem(key) || "{{}}");
    const tbody = document.getElementById("rows");
    function persist() {{ localStorage.setItem(key, JSON.stringify(saved)); }}
    data.forEach((r, i) => {{
      const tr = document.createElement("tr");
      const state = saved[r.paper_id] || {{}};
      const evalValue = state.eval_status || r.eval_status || "";
      const noteValue = state.eval_notes || r.eval_notes || "";
      tr.innerHTML = `
        <td>${{i + 1}}</td>
        <td class="title"><a href="${{r.url || '#'}}" target="_blank" rel="noreferrer">${{r.title}}</a><div class="meta">${{r.authors}}</div><div class="meta">${{r.doi || ''}}</div></td>
        <td>${{r.year || ''}}</td>
        <td>${{r.rank_score_raw || ''}}</td>
        <td>${{r.rank_score_final || ''}}</td>
        <td>${{r.llm_decision || ''}} / ${{r.llm_relevance_score || ''}} / ${{r.llm_novelty_hint || ''}}<div class="meta">${{r.llm_reason || ''}}</div></td>
        <td>${{r.llm_summary || ''}}</td>
        <td>${{r.source_trace || ''}}</td>
        <td>
          <select data-id="${{r.paper_id}}" class="eval">
            <option value="">(none)</option>
            <option value="keep">keep</option>
            <option value="maybe">maybe</option>
            <option value="reject">reject</option>
          </select>
        </td>
        <td><input type="text" data-id="${{r.paper_id}}" class="note" value="${{(noteValue || '').replaceAll('"', '&quot;')}}" /></td>
      `;
      tbody.appendChild(tr);
      tr.querySelector(".eval").value = evalValue;
      tr.querySelector(".eval").addEventListener("change", (e) => {{
        const id = e.target.dataset.id;
        saved[id] = saved[id] || {{}};
        saved[id].eval_status = e.target.value;
        persist();
      }});
      tr.querySelector(".note").addEventListener("input", (e) => {{
        const id = e.target.dataset.id;
        saved[id] = saved[id] || {{}};
        saved[id].eval_notes = e.target.value;
        persist();
      }});
    }});
  </script>
</body>
</html>
"""
    output_path.write_text(html, encoding="utf-8")
