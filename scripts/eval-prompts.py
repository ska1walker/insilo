#!/usr/bin/env python3
"""Manuelles Eval-Skript: schickt die Fixture-Transkripte an einen
echten LLM-Endpunkt und schreibt einen Side-by-Side-Report nach
`/tmp/eval-prompts-<timestamp>.md`.

Use case: vor jedem v0.1.X-Release prüfen, ob die neuen Prompts die
erwartete Output-Qualität gegen Qwen2.5 (oder welches LLM auch immer
auf der Box läuft) liefern. NICHT in CI — Skript braucht eine
laufende LLM-Instanz.

Beispiel:
    python3 scripts/eval-prompts.py \\
        --endpoint http://localhost:11434/v1 \\
        --model qwen2.5:7b-instruct \\
        --api-key sk-local

Optional: --template <allgemein|mandanten|vertrieb|jahres> begrenzt
auf einen Use-Case.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "backend" / "tests" / "eval" / "fixtures"

# Wir importieren die Prompt-Assembler direkt — kein Backend-Boot nötig.
sys.path.insert(0, str(ROOT / "backend"))
from app.tasks.summarize import build_llm_payload, _format_transcript_for_llm  # noqa: E402


# Stand-in templates that mirror what seed.sql ships. Kept in sync with
# `backend/tests/eval/test_prompt_quality.py:SYSTEM_TEMPLATES`. The
# script doesn't read from Postgres so an Olares box isn't required.
SYSTEM_TEMPLATE_BY_FIXTURE: dict[str, str] = {
    "allgemein.yml": "00000000-0000-0000-0000-000000000001",
    "mandanten.yml": "00000000-0000-0000-0000-000000000002",
    "vertrieb.yml": "00000000-0000-0000-0000-000000000003",
    "jahres.yml": "00000000-0000-0000-0000-000000000004",
}


def load_templates_from_seed() -> dict[str, dict[str, Any]]:
    """Parse the live system_prompt + schema + few-shot from supabase/seed.sql.

    We intentionally avoid hitting Postgres so the script works against
    any LLM endpoint (local Ollama, the Olares LiteLLM, OpenAI, …)
    without needing the box to be reachable from the calling laptop.
    """
    # Lightweight extraction: each template lives between
    # `(  '00000000-...',\n  null,\n  '<name>',` and the next `--` line.
    # Since the seed uses Postgres dollar-quoting ($prompt$..$prompt$),
    # we parse by anchors rather than reinventing a SQL parser.
    seed_text = (ROOT / "supabase" / "seed.sql").read_text(encoding="utf-8")
    templates: dict[str, dict[str, Any]] = {}
    # Each template block starts with the literal UUID line.
    for tid in [
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000004",
    ]:
        start = seed_text.find(f"'{tid}'")
        if start < 0:
            continue
        # Slice to next "-- =====" divider
        end = seed_text.find("-- ============================================================", start + 1)
        block = seed_text[start : end if end > 0 else len(seed_text)]
        prompt = _between(block, "$prompt$", "$prompt$")
        schema = _between(block, "$schema$", "$schema$::jsonb")
        few_input = _between(block, "$few$", "$few$,")
        few_output = _between(block, "$few${", "}$few$::jsonb")
        try:
            schema_obj = json.loads(schema) if schema else None
        except json.JSONDecodeError:
            schema_obj = None
        few_output_obj: Any = None
        if few_output:
            try:
                few_output_obj = json.loads("{" + few_output + "}")
            except json.JSONDecodeError:
                few_output_obj = None
        templates[tid] = {
            "system_prompt": prompt or "",
            "output_schema": schema_obj or {},
            "few_shot_input": few_input,
            "few_shot_output": few_output_obj,
        }
    return templates


def _between(text: str, start_marker: str, end_marker: str) -> str | None:
    s = text.find(start_marker)
    if s < 0:
        return None
    s += len(start_marker)
    e = text.find(end_marker, s)
    if e < 0:
        return None
    return text[s:e]


def fetch_summary(
    *, endpoint: str, api_key: str, payload: dict[str, Any], timeout: float
) -> tuple[dict[str, Any] | None, str | None, int]:
    """Send the chat-completions request. Return (parsed_json, raw_content, elapsed_ms)."""
    started = time.monotonic()
    try:
        r = httpx.post(
            f"{endpoint.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=timeout,
        )
    except httpx.HTTPError as exc:
        return None, f"http error: {exc.__class__.__name__}: {exc}", int((time.monotonic() - started) * 1000)
    elapsed_ms = int((time.monotonic() - started) * 1000)
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}: {r.text[:300]}", elapsed_ms
    try:
        data = r.json()
        content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return json.loads(content), content, elapsed_ms
    except (ValueError, json.JSONDecodeError) as exc:
        return None, f"parse error: {exc}", elapsed_ms


def _speakers_enriched(case: dict[str, Any]) -> list[dict[str, Any]]:
    self_name = case.get("self_speaker_name")
    return [
        {
            "id": sp["id"],
            "name": sp["name"],
            "is_self": (self_name is not None and sp["name"] == self_name),
        }
        for sp in case["speakers"]
    ]


def render_report(results: list[dict[str, Any]]) -> str:
    out: list[str] = []
    out.append("# Insilo Prompt-Eval — Live LLM Run")
    out.append("")
    out.append(f"Erzeugt: `{dt.datetime.now().isoformat(timespec='seconds')}`")
    out.append("")
    out.append("| Fixture | Status | Latenz | Felder gefüllt |")
    out.append("|---|---|---:|---|")
    for r in results:
        out.append(
            f"| `{r['case_id']}` | {r['status']} | {r['elapsed_ms']} ms | "
            f"{r['filled_fields']}/{r['total_fields']} |"
        )

    for r in results:
        out.append("")
        out.append(f"## `{r['case_id']}`")
        out.append("")
        out.append(f"**Status:** {r['status']} · **Latenz:** {r['elapsed_ms']} ms · "
                   f"**Felder:** {r['filled_fields']}/{r['total_fields']}")
        if r.get("error"):
            out.append("")
            out.append("```")
            out.append(r["error"])
            out.append("```")
        if r.get("output"):
            out.append("")
            out.append("```json")
            out.append(json.dumps(r["output"], ensure_ascii=False, indent=2))
            out.append("```")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"))
    parser.add_argument("--api-key", default=os.getenv("LLM_API_KEY", "sk-local"))
    parser.add_argument("--model", default=os.getenv("LLM_MODEL", "qwen2.5:7b-instruct"))
    parser.add_argument("--template", choices=["allgemein", "mandanten", "vertrieb", "jahres"])
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--output", default=None,
                        help="Output-Pfad (default: /tmp/eval-prompts-<ts>.md)")
    args = parser.parse_args()

    templates = load_templates_from_seed()

    results: list[dict[str, Any]] = []
    for path in sorted(FIXTURES.glob("*.yml")):
        if args.template and args.template != path.stem:
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        template_id = data["template_id"]
        template = templates.get(template_id)
        if not template:
            print(f"⚠️  Template {template_id} nicht in seed.sql — überspringe {path.name}")
            continue
        for case in data["cases"]:
            case_id = f"{path.stem}.{case['name']}"
            speakers = _speakers_enriched(case)
            transcript = _format_transcript_for_llm(
                case["segments"],
                speakers,
                fallback=" ".join(s["text"] for s in case["segments"]),
            )
            payload = build_llm_payload(
                template=template,
                speakers=speakers,
                transcript_for_llm=transcript,
                model=args.model,
            )
            print(f"→ {case_id} …", flush=True)
            output, raw_or_err, elapsed = fetch_summary(
                endpoint=args.endpoint,
                api_key=args.api_key,
                payload=payload,
                timeout=args.timeout,
            )
            if output is None:
                results.append({
                    "case_id": case_id,
                    "status": "❌ Fehler",
                    "elapsed_ms": elapsed,
                    "filled_fields": 0,
                    "total_fields": 0,
                    "error": raw_or_err,
                    "output": None,
                })
                continue
            total = len(output)
            filled = sum(
                1 for v in output.values()
                if v not in (None, "", [], {})
            )
            results.append({
                "case_id": case_id,
                "status": "✅ OK",
                "elapsed_ms": elapsed,
                "filled_fields": filled,
                "total_fields": total,
                "output": output,
            })

    out_path = args.output or f"/tmp/eval-prompts-{int(time.time())}.md"
    Path(out_path).write_text(render_report(results), encoding="utf-8")
    print(f"\n📄 Report: {out_path}")
    print(f"   {sum(1 for r in results if r['status'] == '✅ OK')}/{len(results)} OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
