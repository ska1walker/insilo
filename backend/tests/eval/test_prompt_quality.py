"""Snapshot-style tests for the Qwen2.5-tuned summary-prompt assembly.

We don't call a real LLM here — that's the job of `scripts/eval-prompts.py`,
which can be run manually against Ollama/LiteLLM. The tests here lock
down the **request shape**: given a fixture transcript and template
metadata, `build_llm_payload` produces messages with the expected
structure (system + optional few-shot + real user) and the agreed
sampling parameters.

Twelve fixtures (3 per template) cover the four use-cases plus
edge-cases like missing speakers, sparse transcripts and explicit
self-marker handling. The fixtures live as YAML files under
`fixtures/` and are loaded via pytest's parametrize indirection.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.tasks.summarize import _format_transcript_for_llm, build_llm_payload

FIXTURES = Path(__file__).parent / "fixtures"

# Hand-curated minimal stand-ins for the seed.sql templates. Keeping
# them in code (not in DB) means the tests don't need a running
# Postgres — they validate the **assembler**, not the schema.
SYSTEM_TEMPLATES: dict[str, dict[str, Any]] = {
    "00000000-0000-0000-0000-000000000001": {
        "name": "Allgemeine Besprechung",
        "system_prompt": (
            "## Aufgabe\nProtokoll des Geschäftsmeetings.\n\n"
            "## Eingabeformat\nDas Transkript zeigt jeden Sprecherbeitrag als `[Sprecher]: Text`.\n\n"
            "## Regeln\n- Verwende ausschließlich Informationen aus dem Transkript.\n\n"
            "## Ausgabe\nJSON nach Schema. Beginne mit `_analyse`."
        ),
        "output_schema": {
            "type": "object",
            "properties": {
                "_analyse": {"type": "string"},
                "kernthemen": {"type": "array"},
                "beschluesse": {"type": "array"},
            },
        },
        "few_shot_input": "[Kai]: Test.\n[Lea]: Auch Test.",
        "few_shot_output": {
            "_analyse": "Knapper Beispiel-Eintrag.",
            "kernthemen": ["Test-Thema"],
            "beschluesse": [],
        },
    },
    "00000000-0000-0000-0000-000000000002": {
        "name": "Mandantengespräch",
        "system_prompt": "## Aufgabe\nAktenprotokoll.\n\n## Regeln\n- Schweigepflicht.\n\n## Ausgabe\nJSON. Beginne mit `_analyse`.",
        "output_schema": {
            "type": "object",
            "properties": {
                "_analyse": {"type": "string"},
                "sachverhalt": {"type": "string"},
                "honorarvereinbarung": {"type": "string"},
            },
        },
        "few_shot_input": "[Anwalt]: Schildern Sie den Sachverhalt.\n[Mandant]: Mündliche Kündigung.",
        "few_shot_output": {
            "_analyse": "Erstgespräch zu mündlicher Kündigung.",
            "sachverhalt": "Mandant wurde mündlich gekündigt.",
            "honorarvereinbarung": None,
        },
    },
    "00000000-0000-0000-0000-000000000003": {
        "name": "Vertriebsgespräch",
        "system_prompt": "## Aufgabe\nBANT-Auswertung.\n\n## Ausgabe\nJSON. Beginne mit `_analyse`.",
        "output_schema": {
            "type": "object",
            "properties": {
                "_analyse": {"type": "string"},
                "bant": {"type": "object"},
                "verkaufschance_einschaetzung": {"type": "string"},
            },
        },
        "few_shot_input": "[Vertrieb]: Welcher Bedarf?\n[Kunde]: Wir wachsen.",
        "few_shot_output": {
            "_analyse": "Discovery-Call ohne Budget-Angabe.",
            "bant": {"budget": None, "need": "Wachstum"},
            "verkaufschance_einschaetzung": "unklar",
        },
    },
    "00000000-0000-0000-0000-000000000004": {
        "name": "Jahresgespräch",
        "system_prompt": "## Aufgabe\nJahresgespräch.\n\n## Ausgabe\nJSON. Beginne mit `_analyse`.",
        "output_schema": {
            "type": "object",
            "properties": {
                "_analyse": {"type": "string"},
                "risikoveraenderungen": {"type": "array"},
                "wiedervorlage": {"type": "string"},
            },
        },
        "few_shot_input": "[Berater]: Was hat sich geändert?\n[Kunde]: Neuer Standort.",
        "few_shot_output": {
            "_analyse": "Bestandskunde mit Standortexpansion.",
            "risikoveraenderungen": ["Neuer Standort"],
            "wiedervorlage": "In 12 Monaten",
        },
    },
}


def _load_fixtures() -> list[tuple[str, dict[str, Any]]]:
    """Flatten the 4 YAML files into (case_id, fixture_dict) tuples for pytest.parametrize."""
    out: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(FIXTURES.glob("*.yml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        template_id = data["template_id"]
        for case in data["cases"]:
            case_id = f"{path.stem}.{case['name']}"
            fixture = dict(case)
            fixture["template_id"] = template_id
            fixture["template"] = SYSTEM_TEMPLATES[template_id]
            out.append((case_id, fixture))
    return out


FIXTURE_CASES = _load_fixtures()


def _speakers_enriched(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert the YAML speakers list into the shape `summarize.py` expects."""
    self_name = fixture.get("self_speaker_name")
    return [
        {
            "id": sp["id"],
            "name": sp["name"],
            "is_self": (self_name is not None and sp["name"] == self_name),
        }
        for sp in fixture["speakers"]
    ]


def test_fixtures_loaded():
    """Sanity: 12 cases across 4 fixture files."""
    assert len(FIXTURE_CASES) == 12, f"expected 12 cases, got {len(FIXTURE_CASES)}"


@pytest.mark.parametrize("case_id,fixture", FIXTURE_CASES, ids=[c[0] for c in FIXTURE_CASES])
def test_payload_structure(case_id: str, fixture: dict[str, Any]) -> None:
    """The assembled chat-completions payload must satisfy our v0.1.40 contract."""
    speakers = _speakers_enriched(fixture)
    transcript_for_llm = _format_transcript_for_llm(
        fixture["segments"],
        speakers,
        fallback=" ".join(s["text"] for s in fixture["segments"]),
    )
    payload = build_llm_payload(
        template=fixture["template"],
        speakers=speakers,
        transcript_for_llm=transcript_for_llm,
        model="test-model",
    )

    # Sampling-Parameter — Qwen2.5-tuned defaults.
    assert payload["model"] == "test-model"
    assert payload["temperature"] == 0.2
    assert payload["top_p"] == 0.8
    assert payload["max_tokens"] == 4096
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["stream"] is False

    msgs = payload["messages"]

    # First message is system, ends with the schema echo.
    assert msgs[0]["role"] == "system"
    assert "Schema:" in msgs[0]["content"]
    assert "_analyse" in msgs[0]["content"]  # Schema-Echo enthält das Pflichtfeld

    # If the template carries a few-shot example: user → assistant → real user
    if fixture["template"].get("few_shot_input"):
        assert len(msgs) == 4, f"expected system+few-shot(user+asst)+real-user, got {len(msgs)}"
        assert msgs[1]["role"] == "user"
        assert msgs[2]["role"] == "assistant"
        assert msgs[3]["role"] == "user"
        # Assistant message must be valid JSON.
        json.loads(msgs[2]["content"])
    else:
        assert len(msgs) == 2
        assert msgs[1]["role"] == "user"

    last_user = msgs[-1]["content"]
    # The real-user message must wrap the transcript in our delimiter.
    assert "=== TRANSKRIPT ===" in last_user
    # And it must carry every speaker's name as a `[Name]:` label.
    for name in fixture["expected_speaker_labels"]:
        assert f"[{name}]" in last_user, f"speaker {name!r} missing from user prompt"


@pytest.mark.parametrize("case_id,fixture", FIXTURE_CASES, ids=[c[0] for c in FIXTURE_CASES])
def test_self_speaker_hint(case_id: str, fixture: dict[str, Any]) -> None:
    """When a fixture marks a speaker as is_self, the system prompt must
    surface them so the LLM can use Sie-form. Without is_self, the hint
    must NOT appear (otherwise the LLM would mis-attribute)."""
    speakers = _speakers_enriched(fixture)
    payload = build_llm_payload(
        template=fixture["template"],
        speakers=speakers,
        transcript_for_llm="dummy",
        model="m",
    )
    system = payload["messages"][0]["content"]

    self_name = fixture.get("self_speaker_name")
    if self_name:
        assert f"»{self_name}«" in system, "self-speaker hint missing"
        assert "in zweiter Person" in system
    else:
        assert "in zweiter Person" not in system


@pytest.mark.parametrize("case_id,fixture", FIXTURE_CASES, ids=[c[0] for c in FIXTURE_CASES])
def test_speaker_annotated_transcript_format(case_id: str, fixture: dict[str, Any]) -> None:
    """The transcript handed to the LLM follows the contract documented
    in the system prompt: each line is `[Sprecher]: Text`."""
    speakers = _speakers_enriched(fixture)
    out = _format_transcript_for_llm(fixture["segments"], speakers, fallback="FALLBACK")
    for seg in fixture["segments"]:
        text = seg["text"].strip()
        if not text:
            continue
        # Find the corresponding speaker name (might be None for the edge case)
        sid = seg.get("speaker")
        if sid is None:
            # _format_transcript_for_llm uses "Sprecher" as fallback label
            assert f"[Sprecher]: {text}" in out or f"[]: {text}" in out
        else:
            name = next(sp["name"] for sp in fixture["speakers"] if sp["id"] == sid)
            assert f"[{name}]: {text}" in out


def test_no_few_shot_falls_back_cleanly():
    """A template without few_shot_input/output must produce a 2-message payload (system + user)."""
    template = {
        "system_prompt": "Test prompt.",
        "output_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
        # neither few_shot_input nor few_shot_output set
    }
    payload = build_llm_payload(
        template=template,
        speakers=[],
        transcript_for_llm="[Anna]: Hallo.",
        model="m",
    )
    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"


def test_custom_fields_merge_into_schema_and_system_prompt():
    """v0.1.41 Lite-Editor: org-eigene Zusatzfelder werden ins Schema
    gemerget UND im System-Prompt als Markdown-Block erwähnt, damit die
    LLM sie kennt."""
    template = {
        "system_prompt": "## Aufgabe\nProtokoll.",
        "output_schema": {
            "type": "object",
            "properties": {"sachverhalt": {"type": "string"}},
        },
        "custom_fields": [
            {"name": "geburtsdatum", "label": "Geburtsdatum",
             "type": "string", "description": "TT.MM.JJJJ"},
            {"name": "zeugen", "label": "Zeugen",
             "type": "array_string", "description": ""},
        ],
    }
    payload = build_llm_payload(
        template=template,
        speakers=[],
        transcript_for_llm="[A]: hi",
        model="m",
    )
    system = payload["messages"][0]["content"]

    # Markdown-Block erwähnt beide Felder mit Label + Typ-Hint
    assert "## Zusätzliche org-spezifische Felder" in system
    assert "**geburtsdatum** (Text)" in system
    assert "**zeugen** (Liste von Texten)" in system
    # Description landet in der Liste
    assert "TT.MM.JJJJ" in system

    # Schema-Echo enthält die neuen Felder
    schema_block = system.split("Schema:\n", 1)[-1]
    schema = json.loads(schema_block)
    assert "geburtsdatum" in schema["properties"]
    assert schema["properties"]["geburtsdatum"]["type"] == "string"
    assert schema["properties"]["geburtsdatum"]["description"] == "TT.MM.JJJJ"
    assert "zeugen" in schema["properties"]
    assert schema["properties"]["zeugen"]["type"] == "array"
    assert schema["properties"]["zeugen"]["items"]["type"] == "string"
    # Original-Property bleibt erhalten
    assert "sachverhalt" in schema["properties"]


def test_custom_fields_empty_list_is_noop():
    """Leere Custom-Fields-Liste: kein Markdown-Block, Schema unverändert."""
    template = {
        "system_prompt": "Test.",
        "output_schema": {
            "type": "object",
            "properties": {"foo": {"type": "string"}},
        },
        "custom_fields": [],
    }
    payload = build_llm_payload(
        template=template, speakers=[], transcript_for_llm="x", model="m",
    )
    system = payload["messages"][0]["content"]
    assert "Zusätzliche org-spezifische Felder" not in system
    schema = json.loads(system.split("Schema:\n", 1)[-1])
    assert list(schema["properties"].keys()) == ["foo"]


def test_custom_fields_collision_with_existing_field_is_ignored():
    """Schutz vor Versehen: ein Custom-Field-Name, der bereits im
    Template-Schema existiert, wird stillschweigend übersprungen."""
    template = {
        "system_prompt": "Test.",
        "output_schema": {
            "type": "object",
            "properties": {"sachverhalt": {"type": "string"}},
        },
        "custom_fields": [
            # Versucht "sachverhalt" zu überschreiben — wird ignoriert
            {"name": "sachverhalt", "label": "Sachverhalt-Custom",
             "type": "array_string", "description": "Custom"},
            {"name": "neues_feld", "label": "Neu",
             "type": "string", "description": ""},
        ],
    }
    payload = build_llm_payload(
        template=template, speakers=[], transcript_for_llm="x", model="m",
    )
    schema = json.loads(payload["messages"][0]["content"].split("Schema:\n", 1)[-1])
    # Original-Feld unverändert
    assert schema["properties"]["sachverhalt"]["type"] == "string"
    assert "description" not in schema["properties"]["sachverhalt"]
    # Nicht-kollidierendes Feld wurde hinzugefügt
    assert "neues_feld" in schema["properties"]


def test_few_shot_output_as_json_string_is_parsed():
    """asyncpg can return JSONB as a string — the assembler must
    handle both dict and string and emit valid JSON for the assistant message."""
    template = {
        "system_prompt": "Test.",
        "output_schema": {"type": "object"},
        "few_shot_input": "[A]: hi",
        # JSONB-as-string path (what asyncpg sometimes gives us)
        "few_shot_output": '{"foo": "bar"}',
    }
    payload = build_llm_payload(
        template=template,
        speakers=[],
        transcript_for_llm="[A]: hi",
        model="m",
    )
    # Assistant message must be valid, re-parsable JSON
    asst = payload["messages"][2]
    assert asst["role"] == "assistant"
    assert json.loads(asst["content"]) == {"foo": "bar"}
