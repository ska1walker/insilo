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
    "kurzfassung": "Kurzfassung",
    "kerninhalt": "Kerninhalt",
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


# ─── Was oben steht ────────────────────────────────────────────────────
#
# Eine Besprechung liefert sechs bis zehn Felder gleichen Gewichts. Wer
# nach einer Aufnahme draufschaut, will drei Dinge: was kam dabei heraus,
# was ist zu tun, worum ging es. Der Rest ist Beleg und darf warten.
#
# Die Reihenfolge steht **hier**, nicht im Bauteil: die Oberfläche bekommt
# sie vom Endpunkt, der Markdown-Export benutzt dieselbe. Sonst liefen
# Ansicht und Datei auseinander, sobald jemand eine Vorlage ändert.
#
# Eine Vorlage kann jedes Feld selbst einordnen — `"x-rang": "kopf"` oder
# `"mehr"` an der Eigenschaft im `output_schema`. Die Liste hier ist die
# Vorbelegung für die Werks-Vorlagen, damit keine davon wandern muss.

KOPF_FELDER: tuple[str, ...] = (
    # 1. Was dabei herauskam — die Kurzfassung in Prosa.
    "kurzfassung",
    "tldr",
    "zusammenfassung",
    "summary",
    "kerninhalt",          # Schnellnotiz: die Notiz selbst ist die Kurzfassung
    # 2. Was zu tun ist. Beschlüsse tragen Verantwortliche und Frist und
    #    stehen deshalb vor den offenen Aufgaben.
    "beschluesse",
    "naechste_schritte",
    "naechste_schritte_mandat",
    "vereinbarte_naechste_schritte",
    "wichtige_termine_fristen",
    "wiedervorlage",
    "follow_up_datum",
    # 3. Worum es ging.
    "kernthemen",
    "anliegen",
    "sachverhalt",
    "schmerzpunkte",       # Vertriebsgespräch
    "bestandsuebersicht",  # Jahresgespräch
)

_KOPF_INDEX = {feld: i for i, feld in enumerate(KOPF_FELDER)}


def rang(feld: str, schema: dict[str, Any] | None = None) -> str:
    """`"kopf"` oder `"mehr"` — was die Vorlage sagt, sonst die Vorbelegung."""
    if _intern(feld):
        return "mehr"
    eigenschaft = ((schema or {}).get("properties") or {}).get(feld)
    if isinstance(eigenschaft, dict):
        gesetzt = eigenschaft.get("x-rang")
        if gesetzt in ("kopf", "mehr"):
            return gesetzt
    return "kopf" if feld in _KOPF_INDEX else "mehr"


def sortieren(
    content: dict[str, Any], schema: dict[str, Any] | None = None
) -> tuple[list[str], list[str]]:
    """Die gefüllten Felder in Kopf und Rest teilen.

    Der Kopf folgt `KOPF_FELDER`; ein Feld, das eine Vorlage selbst
    hochstuft, hängt sich hinten an. Der Rest behält die Reihenfolge des
    Schemas — die hat sich jemand überlegt.

    Leere Felder fallen raus. Ein Kopf mit einer leeren Überschrift ist
    schlimmer als ein kurzer Kopf.
    """
    kopf: list[str] = []
    mehr: list[str] = []
    for feld, wert in content.items():
        if _intern(feld) or _leer(wert):
            continue
        (kopf if rang(feld, schema) == "kopf" else mehr).append(feld)
    kopf.sort(key=lambda f: _KOPF_INDEX.get(f, len(_KOPF_INDEX)))
    return kopf, mehr


def _leer(wert: Any) -> bool:
    if wert is None:
        return True
    if isinstance(wert, str):
        return not wert.strip()
    if isinstance(wert, (list, dict)):
        return not wert
    return False


def _render_summary_sections(
    content: dict[str, Any], schema: dict[str, Any] | None = None
) -> str:
    """Render every top-level key in the summary as its own section.

    Kopf zuerst, dann der Rest — dieselbe Ordnung, die die Oberfläche
    zeigt. Die Datei kennt kein Aufklappen, also steht hier alles
    untereinander; nur eben in der Reihenfolge, in der jemand es liest.
    """
    if not content or not isinstance(content, dict):
        return ""

    kopf, mehr = sortieren(content, schema)
    sections: list[str] = []
    for k in (*kopf, *mehr):
        sec = _render_section(k, content[k])
        if sec:
            sections.append(sec)
    return "\n".join(sections)


def _intern(schluessel: str) -> bool:
    """Denkfelder des Sprachmodells — `_analyse` und Verwandte.

    Seit v0.1.40 lässt der Prompt das Modell erst überlegen und dann
    antworten; die Überlegung landet unter einem Schlüssel mit
    Unterstrich. `frontend/components/summary-view.tsx` klappt sie als
    „LLM-Überlegungen" ein, damit der Hauptteil sauber bleibt — hier
    fehlte dieselbe Regel, und die Überlegung stand als erster Abschnitt
    im Webhook-Rumpf, in `/api/external/v1/.../markdown` und seit
    v0.1.89 in der Datei neben der Aufnahme. Auf der Box gesehen:
    „## Analyse — Das Transkript dokumentiert ausschließlich einen
    technischen Testlauf …" als Kopf einer Zusammenfassung.

    Wer die Überlegung braucht, findet sie in `summaries.content`. In
    einem Protokoll, das jemand in die Akte legt, hat sie nichts verloren.
    """
    return schluessel.startswith("_")


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
    `summary` keys expected: content (the template-shaped JSON), llm_model,
        and optionally `schema` — das `output_schema` der Vorlage, aus dem
        `x-rang` gelesen wird. Fehlt es, greift die Vorbelegung in
        `KOPF_FELDER`.
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
            rendered = _render_summary_sections(content, summary.get("schema"))
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
