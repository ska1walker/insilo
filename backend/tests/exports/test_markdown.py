"""Tests for the meeting-markdown renderer.

The renderer is a pure function — these tests pass in plain dicts that
mirror what `routers/meetings.py:get_meeting` produces.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.exports.markdown import render_meeting_markdown


def _meeting(**overrides):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Strategie Q2",
        "recorded_at": datetime(2026, 5, 12, 14, 30, tzinfo=UTC),
        "duration_sec": 1800,
        "language": "de",
    }
    base.update(overrides)
    return base


def _transcript(**overrides):
    base = {
        "segments": [
            {"start": 0, "speaker": "spk_kai", "text": "Willkommen zum Quartalstermin."},
            {"start": 12, "speaker": "spk_lea", "text": "Danke. Ich habe drei Themen mitgebracht."},
        ],
        "speakers": [
            {"id": "spk_kai", "name": "Kai Böhm"},
            {"id": "spk_lea", "name": "Lea Schmidt"},
        ],
        "full_text": "Willkommen zum Quartalstermin. Danke. Ich habe drei Themen mitgebracht.",
        "language": "de",
    }
    base.update(overrides)
    return base


def test_renders_frontmatter_and_title():
    md = render_meeting_markdown(
        meeting=_meeting(),
        transcript=_transcript(),
        summary=None,
        tags=[{"name": "Strategie", "color": "#000"}],
        template_name="Allgemeine Besprechung",
    )
    assert md.startswith("---\n")
    assert "source: insilo" in md
    assert "title: Strategie Q2" in md
    assert "duration_min: 30" in md
    assert "language: de" in md
    assert "template: Allgemeine Besprechung" in md
    assert "- Strategie" in md  # tag in list_fields
    assert "- Kai Böhm" in md  # speaker
    assert "# Strategie Q2" in md
    assert "**Datum:** 12.05.2026" in md
    assert "**Dauer:** 30 min" in md


def test_renders_summary_sections_with_tasks_as_checklist():
    summary = {
        "content": {
            "kernthemen": ["Roadmap-Update", "Hiring-Plan"],
            "beschluesse": [
                {"beschluss": "Neuen DevOps-Lead suchen", "verantwortlich": "Kai", "frist": "Ende Mai"},
                {"beschluss": "Cloud-Budget freigeben", "verantwortlich": "Lea"},
            ],
            "naechste_schritte": [
                {"text": "Briefing für Recruiter erstellen", "verantwortlich": "Kai", "frist": "16.05."},
            ],
            "offene_fragen": [],  # leere Sektion → muss übersprungen werden
        },
        "llm_model": "qwen2.5:7b-instruct",
    }
    md = render_meeting_markdown(
        meeting=_meeting(),
        transcript=_transcript(),
        summary=summary,
        tags=None,
        template_name="Allgemeine Besprechung",
    )
    # Section headers
    assert "## Kernthemen" in md
    assert "## Beschlüsse" in md
    assert "## Offene Aufgaben" in md  # naechste_schritte gets pretty-renamed
    # Bullet list for plain strings
    assert "- Roadmap-Update" in md
    assert "- Hiring-Plan" in md
    # Task-shaped objects render as GFM checklist with assignee + due
    assert "- [ ] Neuen DevOps-Lead suchen — Kai, fällig Ende Mai" in md
    assert "- [ ] Cloud-Budget freigeben — Lea" in md
    assert "- [ ] Briefing für Recruiter erstellen — Kai, fällig 16.05." in md
    # Empty section should be skipped, NOT stubbed with "—"
    assert "## Offene Fragen" not in md


def test_skips_transcript_when_disabled_and_renders_when_enabled():
    md_with = render_meeting_markdown(
        meeting=_meeting(),
        transcript=_transcript(),
        summary=None,
        tags=None,
        template_name=None,
        include_transcript=True,
    )
    assert "## Volltranskript" in md_with
    assert "[0:00] **Kai Böhm**: Willkommen zum Quartalstermin." in md_with
    assert "[0:12] **Lea Schmidt**: Danke." in md_with

    md_without = render_meeting_markdown(
        meeting=_meeting(),
        transcript=_transcript(),
        summary=None,
        tags=None,
        template_name=None,
        include_transcript=False,
    )
    assert "## Volltranskript" not in md_without


def test_handles_unknown_summary_keys_gracefully():
    """A custom org template can return keys we don't pretty-name —
    the renderer should still produce sensible Markdown."""
    summary = {
        "content": {
            "custom_thema": "Quartalsreview",
            "weitere_punkte": ["Punkt A", "Punkt B"],
        }
    }
    md = render_meeting_markdown(
        meeting=_meeting(),
        transcript=None,
        summary=summary,
        tags=None,
        template_name=None,
    )
    # Unknown keys → title-case fallback
    assert "## Custom Thema" in md
    assert "Quartalsreview" in md
    assert "## Weitere Punkte" in md
    assert "- Punkt A" in md
    assert "- Punkt B" in md


def test_renders_with_no_summary_and_no_transcript():
    """An early-state meeting (before transcript/summary land) should
    still produce valid Markdown — frontmatter + title + meta only."""
    md = render_meeting_markdown(
        meeting=_meeting(),
        transcript=None,
        summary=None,
        tags=None,
        template_name=None,
    )
    assert md.startswith("---\n")
    assert "# Strategie Q2" in md
    # No summary or transcript sections
    assert "##" not in md
