"""Render a meeting + transcript + summary into a single Markdown document.

This is a **pure function** — no I/O, no DB calls. Inputs are the rows we
already fetch in `routers/meetings.py:get_meeting`. The output is what
downstream consumers (the webhook payload, the `/api/external/v1/.../markdown`
endpoint, future file-drops) deliver.

The summary content shape is template-defined, so the renderer walks the
JSON generically: top-level keys become H2 sections; lists of strings
become bullet lists; lists of objects with task-like fields
(`verantwortlich`, `frist`, `beschluss`) become GFM checklists; everything
else falls back to a readable representation. We pretty-print known
German section keys (`kernthemen` → "Kernthemen") and pass everything
else through `title()`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# ─── Pretty section titles ─────────────────────────────────────────────

_SECTION_TITLES: dict[str, str] = {
    "anwesende": "Anwesende",
    "kernthemen": "Kernthemen",
    "wichtige_aussagen": "Wichtige Aussagen",
    "beschluesse": "Beschlüsse",
    "offene_fragen": "Offene Fragen",
    "naechste_schritte": "Offene Aufgaben",
    "naechste_schritte_mandat": "Offene Aufgaben",
    "vereinbarte_naechste_schritte": "Offene Aufgaben",
    "sachverhalt": "Sachverhalt",
    "rechtsfragen": "Rechtsfragen",
    "eingebrachte_unterlagen": "Eingebrachte Unterlagen",
    "vereinbarte_leistungen": "Vereinbarte Leistungen",
    "wichtige_termine_fristen": "Wichtige Termine & Fristen",
    "honorarvereinbarung": "Honorarvereinbarung",
    "mandantenname": "Mandant",
    "kunde": "Kunde",
    "schmerzpunkte": "Schmerzpunkte",
    "aktuelle_loesung": "Aktuelle Lösung",
    "bant": "BANT-Analyse",
    "einwaende": "Einwände",
    "follow_up_datum": "Follow-up",
    "verkaufschance_einschaetzung": "Einschätzung der Verkaufschance",
    "bestandsuebersicht": "Bestandsübersicht",
    "risikoveraenderungen": "Risikoveränderungen",
    "cross_selling_potenziale": "Cross-Selling-Potenziale",
    "kundenwuensche": "Kundenwünsche",
    "wiedervorlage": "Wiedervorlage",
    "zusammenfassung": "Zusammenfassung",
    "tldr": "Zusammenfassung",
}

# Object keys that signal "this list represents tasks/decisions" — they
# get rendered as a GFM checklist with assignee + due-date suffix.
_TASK_OBJECT_KEYS = {"beschluss", "aufgabe", "task", "naechster_schritt", "schritt"}
_ASSIGNEE_KEYS = ("verantwortlich", "owner", "person", "wer")
_DUE_KEYS = ("frist", "deadline", "bis", "due")


def _pretty(key: str) -> str:
    if key in _SECTION_TITLES:
        return _SECTION_TITLES[key]
    return key.replace("_", " ").title()


def _format_seconds(total: int | None) -> str:
    if not total:
        return "0:00"
    minutes, secs = divmod(int(total), 60)
    return f"{minutes}:{secs:02d}"


def _format_de_date(dt: datetime | str | None) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt
    return dt.strftime("%d.%m.%Y")


def _iso(dt: datetime | str | None) -> str:
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


# ─── Section renderers ─────────────────────────────────────────────────

def _looks_like_task_list(items: list[Any]) -> bool:
    """A list of dicts where the dicts carry task-like fields."""
    if not items:
        return False
    if not all(isinstance(it, dict) for it in items):
        return False
    keys: set[str] = set()
    for it in items:
        keys.update(it.keys())
    return bool(
        keys & _TASK_OBJECT_KEYS
        or any(k in keys for k in _ASSIGNEE_KEYS)
        or any(k in keys for k in _DUE_KEYS)
    )


def _render_task_item(item: dict[str, Any]) -> str:
    text_parts: list[str] = []
    for k in ("beschluss", "aufgabe", "task", "naechster_schritt", "schritt", "text"):
        if item.get(k):
            text_parts.append(str(item[k]).strip())
            break
    if not text_parts:
        # No designated text field — fall back to the first non-meta value.
        for k, v in item.items():
            if k in _ASSIGNEE_KEYS or k in _DUE_KEYS:
                continue
            if isinstance(v, str) and v.strip():
                text_parts.append(v.strip())
                break

    suffix_parts: list[str] = []
    assignee = next((item[k] for k in _ASSIGNEE_KEYS if item.get(k)), None)
    due = next((item[k] for k in _DUE_KEYS if item.get(k)), None)
    if assignee:
        suffix_parts.append(str(assignee).strip())
    if due:
        suffix_parts.append(f"fällig {str(due).strip()}")

    text = " ".join(text_parts) or "(ohne Beschreibung)"
    if suffix_parts:
        return f"- [ ] {text} — {', '.join(suffix_parts)}"
    return f"- [ ] {text}"


def _render_value(value: Any, indent: int = 0) -> list[str]:
    """Render an arbitrary JSON value into Markdown lines."""
    pad = "  " * indent
    if value is None or value == "":
        return []
    if isinstance(value, str):
        return [pad + value.strip()] if value.strip() else []
    if isinstance(value, (int, float)):
        return [pad + str(value)]
    if isinstance(value, list):
        if not value:
            return []
        if _looks_like_task_list(value):
            return [_render_task_item(it) for it in value if isinstance(it, dict)]
        lines: list[str] = []
        for it in value:
            if isinstance(it, dict):
                # Render as a sub-block: first non-empty string becomes
                # the bullet, the rest become indented kv lines.
                primary: str | None = None
                rest: list[tuple[str, Any]] = []
                for k, v in it.items():
                    if primary is None and isinstance(v, str) and v.strip():
                        primary = v.strip()
                        continue
                    rest.append((k, v))
                if primary is None and it:
                    primary = "(–)"
                lines.append(f"{pad}- {primary}")
                for k, v in rest:
                    sub = _render_value(v, indent=indent + 1)
                    if not sub:
                        continue
                    if len(sub) == 1:
                        lines.append(f"{pad}  - **{_pretty(k)}:** {sub[0].strip()}")
                    else:
                        lines.append(f"{pad}  - **{_pretty(k)}:**")
                        lines.extend("  " + s for s in sub)
            else:
                rendered = _render_value(it, indent=indent)
                if rendered:
                    lines.append(f"{pad}- {rendered[0].strip()}")
                    lines.extend(rendered[1:])
        return lines
    if isinstance(value, dict):
        if not value:
            return []
        lines = []
        for k, v in value.items():
            sub = _render_value(v, indent=indent + 1)
            if not sub:
                continue
            if len(sub) == 1:
                lines.append(f"{pad}- **{_pretty(k)}:** {sub[0].strip()}")
            else:
                lines.append(f"{pad}- **{_pretty(k)}:**")
                lines.extend(sub)
        return lines
    return [pad + str(value)]


def _render_section(key: str, value: Any) -> str:
    """Render one top-level summary key as an H2 section.

    Returns an empty string if the value is empty — empty sections are
    skipped, not stubbed with "—".
    """
    rendered = _render_value(value)
    if not rendered:
        return ""
    body = "\n".join(rendered)
    return f"## {_pretty(key)}\n\n{body}\n"


def _render_summary_sections(content: dict[str, Any]) -> str:
    """Render every top-level key in the summary as its own section."""
    if not content or not isinstance(content, dict):
        return ""

    # If the LLM returned a short summary string under a known alias,
    # promote it to the lead "Zusammenfassung" section.
    sections: list[str] = []
    leading_keys = ("tldr", "zusammenfassung", "summary")
    for k in leading_keys:
        if k in content and content[k]:
            sec = _render_section(k, content[k])
            if sec:
                sections.append(sec)

    seen = set(leading_keys)
    for k, v in content.items():
        if k in seen:
            continue
        sec = _render_section(k, v)
        if sec:
            sections.append(sec)
    return "\n".join(sections)


# ─── Frontmatter + meta line ───────────────────────────────────────────

def _yaml_value(v: Any) -> str:
    """Minimal YAML scalar escape — we never emit nested structures here."""
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(c in s for c in (":", "#", "'", '"', "\n", "[", "]", "{", "}", ",", "&", "*")):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _render_frontmatter(fields: dict[str, Any], list_fields: dict[str, list[str]]) -> str:
    lines = ["---"]
    for k, v in fields.items():
        lines.append(f"{k}: {_yaml_value(v)}")
    for k, items in list_fields.items():
        if not items:
            lines.append(f"{k}: []")
        else:
            lines.append(f"{k}:")
            for it in items:
                lines.append(f"  - {_yaml_value(it)}")
    lines.append("---")
    return "\n".join(lines)


# ─── Transcript ────────────────────────────────────────────────────────

def _render_transcript(segments: list[dict[str, Any]], speakers: list[dict[str, Any]]) -> str:
    if not segments:
        return ""
    # Map speaker-id → display name
    name_by_id: dict[str, str] = {}
    for s in speakers or []:
        sid = s.get("id")
        name = s.get("name")
        if sid and name:
            name_by_id[sid] = name

    lines: list[str] = []
    for seg in segments:
        start = seg.get("start") or 0
        try:
            start_s = int(float(start))
        except (TypeError, ValueError):
            start_s = 0
        ts = _format_seconds(start_s)
        sid = seg.get("speaker") or ""
        speaker_label = name_by_id.get(sid, sid or "Sprecher")
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"[{ts}] **{speaker_label}**: {text}")
    return "\n\n".join(lines)


# ─── Public API ────────────────────────────────────────────────────────

def render_meeting_markdown(
    *,
    meeting: dict[str, Any],
    transcript: dict[str, Any] | None,
    summary: dict[str, Any] | None,
    tags: list[dict[str, Any]] | None = None,
    template_name: str | None = None,
    include_transcript: bool = True,
) -> str:
    """Build the canonical Markdown for one meeting.

    `meeting` keys expected: id, title, recorded_at, duration_sec, language.
    `transcript` keys expected: segments (list of {start, text, speaker}),
        speakers (list of {id, name}), full_text, language.
    `summary` keys expected: content (the template-shaped JSON), llm_model.
    `tags`: list of {name, color}. `template_name`: pretty name for the
    frontmatter + header line.
    """
    title = str(meeting.get("title") or "Unbenanntes Meeting").strip()
    recorded_at = meeting.get("recorded_at")
    duration_sec = int(meeting.get("duration_sec") or 0)
    duration_min = max(1, round(duration_sec / 60)) if duration_sec else 0
    language = str(meeting.get("language") or "de")
    meeting_id = str(meeting.get("id") or "")

    speakers = (transcript or {}).get("speakers") or []
    speaker_names = [s.get("name") for s in speakers if isinstance(s, dict) and s.get("name")]
    tag_names = [t.get("name") for t in (tags or []) if isinstance(t, dict) and t.get("name")]

    frontmatter = _render_frontmatter(
        fields={
            "source": "insilo",
            "meeting_id": meeting_id,
            "title": title,
            "date": _iso(recorded_at),
            "duration_min": duration_min,
            "template": template_name or "",
            "language": language,
        },
        list_fields={
            "tags": tag_names,
            "speakers": speaker_names,
        },
    )

    # Title + meta line
    parts: list[str] = [frontmatter, "", f"# {title}", ""]
    meta_bits: list[str] = []
    date_de = _format_de_date(recorded_at)
    if date_de:
        meta_bits.append(f"**Datum:** {date_de}")
    if duration_min:
        meta_bits.append(f"**Dauer:** {duration_min} min")
    if template_name:
        meta_bits.append(f"**Vorlage:** {template_name}")
    if meta_bits:
        parts.append(" · ".join(meta_bits))
        parts.append("")

    # Summary sections
    if summary and isinstance(summary, dict):
        content = summary.get("content") or {}
        if isinstance(content, dict) and content:
            rendered = _render_summary_sections(content)
            if rendered:
                parts.append(rendered)

    # Transcript
    if include_transcript and transcript:
        segs = transcript.get("segments") or []
        if segs:
            parts.append("## Volltranskript")
            parts.append("")
            parts.append(_render_transcript(segs, speakers))
            parts.append("")

    # Trim repeated blank lines but keep the trailing newline.
    out = "\n".join(parts).rstrip() + "\n"
    return out
