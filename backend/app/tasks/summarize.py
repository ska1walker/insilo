"""Celery task: generate a structured summary of a transcribed meeting via Ollama."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from celery import shared_task

from app.config import settings
from app.llm_config import load_llm_config
from app.worker import celery_app  # noqa: F401 -- side-effect: registers worker

log = logging.getLogger(__name__)


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )


async def _set_status(
    conn: asyncpg.Connection, meeting_id: UUID, status: str, error: str | None = None
) -> None:
    await conn.execute(
        """
        update public.meetings
        set status = $2, error_message = $3, updated_at = now()
        where id = $1
        """,
        meeting_id,
        status,
        error,
    )


def _resolve_prompt(template: dict[str, Any], locale: str) -> str | None:
    """Pick the right prompt body for `locale` from a template row.

    Resolution order (v0.1.46+):
      1. Customization's locale-specific prompt (`c.system_prompts->>locale`)
      2. Customization's DE prompt (`c.system_prompts->>'de'`)
      3. Customization's legacy TEXT prompt (`c.system_prompt`)
      4. System template's locale-specific prompt (`t.system_prompts->>locale`)
      5. System template's DE prompt
      6. System template's legacy TEXT prompt

    Returns the first non-empty string, or None if nothing usable exists.
    """
    def _from(jsonb_val: Any, code: str) -> str | None:
        if jsonb_val is None:
            return None
        if isinstance(jsonb_val, str):
            try:
                jsonb_val = json.loads(jsonb_val)
            except json.JSONDecodeError:
                return None
        if not isinstance(jsonb_val, dict):
            return None
        v = jsonb_val.get(code)
        return v if isinstance(v, str) and v.strip() else None

    candidates = [
        _from(template.get("c_system_prompts"), locale),
        _from(template.get("c_system_prompts"), "de"),
        template.get("c_system_prompt"),
        _from(template.get("t_system_prompts"), locale),
        _from(template.get("t_system_prompts"), "de"),
        template.get("t_system_prompt"),
    ]
    for c in candidates:
        if isinstance(c, str) and c.strip():
            return c
    return None


# LLM-bound boilerplate strings, localized so the model sees a coherent
# language signal (system_prompt + user-wrapper + self-speaker-hint).
# Falls back to DE when an unknown locale is requested.
_WRAP_USER: dict[str, tuple[str, str, str]] = {
    "de": (
        "Hier folgt das Transkript der Besprechung. Analysiere es streng nach den "
        "Vorgaben des Systems und gib AUSSCHLIESSLICH ein JSON-Objekt zurück, das "
        "dem definierten Output-Schema entspricht.",
        "TRANSKRIPT", "ENDE TRANSKRIPT",
    ),
    "en": (
        "The following is the meeting transcript. Analyse it strictly according to "
        "the system instructions and return ONLY a JSON object that matches the "
        "defined output schema.",
        "TRANSCRIPT", "END TRANSCRIPT",
    ),
    "fr": (
        "Voici la transcription de la réunion. Analyse-la strictement selon les "
        "instructions du système et renvoie UNIQUEMENT un objet JSON conforme au "
        "schéma de sortie défini.",
        "TRANSCRIPTION", "FIN TRANSCRIPTION",
    ),
    "es": (
        "A continuación la transcripción de la reunión. Analízala estrictamente "
        "según las instrucciones del sistema y devuelve EXCLUSIVAMENTE un objeto "
        "JSON conforme al esquema de salida definido.",
        "TRANSCRIPCIÓN", "FIN TRANSCRIPCIÓN",
    ),
    "it": (
        "Segue la trascrizione della riunione. Analizzala rigorosamente secondo le "
        "istruzioni del sistema e restituisci ESCLUSIVAMENTE un oggetto JSON "
        "conforme allo schema di output definito.",
        "TRASCRIZIONE", "FINE TRASCRIZIONE",
    ),
}

_SELF_SPEAKER_HINT: dict[str, str] = {
    "de": "\n\nHinweis: Sprecher »{name}« ist die Nutzerin/der Nutzer dieses Systems. "
          "Beschlüsse und Aufgaben dürfen — wo es natürlich wirkt — in zweiter Person "
          "formuliert werden (»Sie haben …«, »Ihnen obliegt …«) statt in dritter.",
    "en": "\n\nNote: speaker \"{name}\" is the user of this system. Decisions and "
          "tasks may — where natural — be phrased in the second person (\"you "
          "agreed …\", \"it falls to you to …\") rather than the third.",
    "fr": "\n\nNote : le locuteur « {name} » est l'utilisateur de ce système. Les "
          "décisions et tâches peuvent — lorsque cela paraît naturel — être "
          "formulées à la deuxième personne (« vous avez accepté … », « il vous "
          "revient de … ») plutôt qu'à la troisième.",
    "es": "\n\nNota: el hablante «{name}» es el usuario de este sistema. Las "
          "decisiones y tareas pueden — cuando suene natural — formularse en "
          "segunda persona formal («usted aceptó …», «le corresponde …») en lugar "
          "de la tercera.",
    "it": "\n\nNota: il parlante «{name}» è l'utente di questo sistema. Le "
          "decisioni e i compiti possono — quando suoni naturale — essere "
          "formulati in seconda persona formale («Lei ha accettato …», «spetta a "
          "Lei …») anziché in terza.",
}

_CUSTOM_FIELDS_HEADER: dict[str, tuple[str, str, str, str]] = {
    "de": (
        "## Zusätzliche org-spezifische Felder",
        "Diese Felder sind von der Organisation ergänzt. Fülle sie aus,",
        "wenn das Transkript die Information klar liefert; sonst `null`.",
        "Liste von Texten",
    ),
    "en": (
        "## Additional organisation-specific fields",
        "These fields were added by the organisation. Fill them in",
        "when the transcript provides the information clearly; otherwise `null`.",
        "List of strings",
    ),
    "fr": (
        "## Champs supplémentaires spécifiques à l'organisation",
        "Ces champs ont été ajoutés par l'organisation. Remplissez-les",
        "lorsque la transcription fournit l'information clairement ; sinon `null`.",
        "Liste de chaînes",
    ),
    "es": (
        "## Campos adicionales específicos de la organización",
        "Estos campos los ha añadido la organización. Rellénelos",
        "cuando la transcripción aporte la información con claridad; si no, `null`.",
        "Lista de textos",
    ),
    "it": (
        "## Campi aggiuntivi specifici dell'organizzazione",
        "Questi campi sono stati aggiunti dall'organizzazione. Compilali",
        "quando la trascrizione fornisce l'informazione in modo chiaro; altrimenti `null`.",
        "Lista di stringhe",
    ),
}

_TEXT_TYPE_LABEL: dict[str, str] = {
    "de": "Text", "en": "Text", "fr": "Texte", "es": "Texto", "it": "Testo",
}

_FALLBACK_SPEAKER_LABEL: dict[str, str] = {
    "de": "Sprecher", "en": "Speaker", "fr": "Locuteur", "es": "Hablante", "it": "Parlante",
}


def _wrap_user_prompt(transcript_text: str, locale: str = "de") -> str:
    intro, start, end = _WRAP_USER.get(locale) or _WRAP_USER["de"]
    return (
        f"{intro}\n\n"
        f"=== {start} ===\n{transcript_text}\n=== {end} ==="
    )


def _format_transcript_for_llm(
    segments: list[dict[str, Any]] | None,
    speakers: list[dict[str, Any]] | None,
    fallback: str,
    locale: str = "de",
) -> str:
    """Bau ein speaker-annotiertes Transkript für die LLM-Eingabe.

    Hat das Transkript Speaker-Labels (Diarization ist gelaufen, der User
    hat Namen vergeben), wird daraus eine `[Name]: Text`-Zeile pro
    Segment — die LLM kann dann Beschlüsse Personen zuordnen.

    Ohne brauchbare Labels fallen wir auf den Plain-Text-Fallback zurück.
    """
    if not segments:
        return fallback
    name_by_id: dict[str, str] = {}
    for s in speakers or []:
        sid = s.get("id")
        name = s.get("name")
        if sid and name:
            name_by_id[sid] = name

    lines: list[str] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        sid = seg.get("speaker") or ""
        fallback_label = _FALLBACK_SPEAKER_LABEL.get(locale, _FALLBACK_SPEAKER_LABEL["de"])
        label = name_by_id.get(sid, sid or fallback_label)
        lines.append(f"[{label}]: {text}")
    if not lines:
        return fallback
    return "\n".join(lines)


def _self_speaker_hint(
    speakers: list[dict[str, Any]] | None, locale: str = "de"
) -> str:
    """Optionaler Hinweis ans Modell: einer der Sprecher ist der Nutzer.

    Wenn das System weiß welcher Sprecher der User ist, kann die Summary
    Beschlüsse aus der Sie-Perspektive formulieren ("Sie hatten zugesagt
    …" statt "Kai hatte zugesagt …"). Greift nur wenn ein Org-Speaker
    mit is_self=true existiert und in diesem Meeting gesprochen hat.
    """
    if not speakers:
        return ""
    template = _SELF_SPEAKER_HINT.get(locale) or _SELF_SPEAKER_HINT["de"]
    for s in speakers:
        if s.get("is_self") and s.get("name"):
            return template.format(name=s["name"])
    return ""


def _merge_custom_fields(
    schema: dict[str, Any],
    custom_fields: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Append org-specific extra fields onto a template schema.

    Only `string` and `array_string` types are supported (v0.1.41 Lite).
    Returns a NEW schema dict — the input is not mutated. Collisions
    with existing properties are silently skipped (the validation in
    the router already prevents this, but defense-in-depth is cheap).
    """
    if not custom_fields:
        return schema

    out = dict(schema)
    props = dict(out.get("properties") or {})
    for cf in custom_fields:
        name = cf.get("name")
        if not name or name in props:
            continue
        if cf.get("type") == "array_string":
            field_schema: dict[str, Any] = {
                "type": "array",
                "items": {"type": "string"},
            }
        else:
            field_schema = {"type": "string"}
        if cf.get("description"):
            field_schema["description"] = cf["description"]
        props[name] = field_schema
    out["properties"] = props
    return out


def _custom_fields_prompt_block(
    custom_fields: list[dict[str, Any]] | None, locale: str = "de"
) -> str:
    """Render a Markdown block listing org-specific extra fields so the
    LLM knows they exist even before reading the schema echo."""
    if not custom_fields:
        return ""
    header, line1, line2, list_type = (
        _CUSTOM_FIELDS_HEADER.get(locale) or _CUSTOM_FIELDS_HEADER["de"]
    )
    text_type = _TEXT_TYPE_LABEL.get(locale, _TEXT_TYPE_LABEL["de"])
    lines = ["", header, line1, line2, ""]
    for cf in custom_fields:
        label = cf.get("label") or cf.get("name") or ""
        desc = cf.get("description") or ""
        type_hint = list_type if cf.get("type") == "array_string" else text_type
        line = f"- **{cf.get('name')}** ({type_hint}) — {label}"
        if desc:
            line += f": {desc}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def build_llm_payload(
    *,
    template: dict[str, Any],
    speakers: list[dict[str, Any]] | None,
    transcript_for_llm: str,
    model: str,
    locale: str = "de",
) -> dict[str, Any]:
    """Compose the OpenAI-compatible chat-completions payload for one meeting.

    Pure function — extracted so we can unit-test the message-assembly
    contract (system + optional few-shot + real user) without booting
    Celery or the DB. Called from `_do_summarize` for production, and
    from `backend/tests/eval/test_prompt_quality.py` for snapshots.

    Args:
        template: row-like dict with keys `system_prompt`, `output_schema`,
            and optional `few_shot_input`, `few_shot_output`,
            `custom_fields` (v0.1.41 Lite-Schema-Editor).
        speakers: enriched speakers list (each entry can carry `is_self`).
        transcript_for_llm: speaker-annotated transcript ready for the
            user message body.
        model: model name as the LLM gateway expects it.
    """
    schema_raw = template.get("output_schema")
    if isinstance(schema_raw, str):
        schema = json.loads(schema_raw)
    else:
        schema = schema_raw or {}

    # v0.1.41 — org-spezifische Zusatzfelder ins Schema mergen, bevor
    # wir es echoen. Few-Shot bleibt unverändert (zeigt nur die
    # Pflichtfelder); der Markdown-Block weiter oben sagt der LLM, dass
    # zusätzliche Felder vorhanden sind.
    raw_custom = template.get("custom_fields")
    if isinstance(raw_custom, str):
        try:
            custom_fields = json.loads(raw_custom)
        except json.JSONDecodeError:
            custom_fields = []
    elif isinstance(raw_custom, list):
        custom_fields = raw_custom
    else:
        custom_fields = []
    effective_schema = _merge_custom_fields(schema, custom_fields)

    # System-Prompt: erst die Template-Anweisungen (Markdown-strukturiert,
    # siehe seed.sql), dann ggf. der Self-Speaker-Hinweis, dann die
    # Custom-Field-Liste, dann das Schema-Echo. Für Qwen2.5 Q4 ist das
    # Schema-Echo Pflicht — der response_format=json_object reicht
    # alleine nicht zuverlässig.
    system_content = (
        (template.get("system_prompt") or "")
        + _self_speaker_hint(speakers, locale)
        + _custom_fields_prompt_block(custom_fields, locale)
        + "\n\nSchema:\n"
        + json.dumps(effective_schema, ensure_ascii=False)
    )

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
    ]

    # Few-Shot — eingehängt als zusätzliche User→Assistant-Runde vor
    # dem realen Transkript. Bei 14B Q4 mit >5 Schema-Feldern bringt das
    # spürbar saubereren JSON-Output (siehe v0.1.40-Plan).
    few_shot_input = template.get("few_shot_input")
    few_shot_output_raw = template.get("few_shot_output")
    if few_shot_input and few_shot_output_raw:
        if isinstance(few_shot_output_raw, str):
            try:
                few_shot_output_obj = json.loads(few_shot_output_raw)
            except json.JSONDecodeError:
                few_shot_output_obj = None
        else:
            few_shot_output_obj = few_shot_output_raw
        if few_shot_output_obj is not None:
            messages.append({
                "role": "user",
                "content": _wrap_user_prompt(few_shot_input, locale),
            })
            messages.append({
                "role": "assistant",
                "content": json.dumps(few_shot_output_obj, ensure_ascii=False),
            })

    messages.append({"role": "user", "content": _wrap_user_prompt(transcript_for_llm, locale)})

    # OpenAI-compatible JSON-mode (works for LiteLLM proxy and Ollama's
    # native /v1 endpoint). Sampling-Parameter folgen Qwen2.5-Community-
    # Empfehlungen für strukturierte Tasks (temp 0.2, top_p 0.8).
    return {
        "model": model,
        "stream": False,
        "temperature": 0.2,
        "top_p": 0.8,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
        "messages": messages,
    }


async def _do_summarize(meeting_id: UUID) -> dict[str, Any]:
    conn = await _connect()
    try:
        meeting = await conn.fetchrow(
            """
            select m.id, m.org_id, m.template_id,
                   t.full_text, t.word_count,
                   t.segments, t.speakers
            from public.meetings m
            left join public.transcripts t on t.meeting_id = m.id
            where m.id = $1 and m.deleted_at is null
            """,
            meeting_id,
        )
        if not meeting:
            return {"status": "skipped", "reason": "no meeting"}
        if not meeting["full_text"]:
            return {"status": "skipped", "reason": "no transcript"}

        # Parse JSONB segments + speakers (asyncpg gives them back as strings).
        raw_segments = meeting["segments"]
        if isinstance(raw_segments, str):
            raw_segments = json.loads(raw_segments)
        raw_speakers = meeting["speakers"]
        if isinstance(raw_speakers, str):
            raw_speakers = json.loads(raw_speakers)
        # Annotate speakers with is_self by looking up the org-speaker row
        # they point to. transcripts.speakers entries with id="org_<uuid>"
        # carry an org_speaker_id we can resolve directly.
        speakers_enriched: list[dict[str, Any]] = []
        for s in (raw_speakers or []):
            entry = dict(s)
            org_sid = entry.get("org_speaker_id")
            if org_sid:
                row = await conn.fetchrow(
                    "select is_self from public.org_speakers where id = $1",
                    UUID(org_sid),
                )
                entry["is_self"] = bool(row and row["is_self"])
            speakers_enriched.append(entry)

        # Pick template: explicit on meeting, else the system default. Apply
        # the org's prompt customization (from /einstellungen) if present —
        # otherwise the seeded `system_prompt` is used.
        #
        # v0.1.46+: prompts can be authored per locale in `system_prompts JSONB`.
        # We resolve the meeting-creator's UI locale (with org-default + 'de'
        # fallback) and pick the matching prompt. If no locale-specific entry
        # exists for either the customization or the system template, we fall
        # back to DE, then to the legacy `system_prompt TEXT` column.
        template_id = meeting["template_id"] or UUID(settings.default_template_id)
        locale_row = await conn.fetchrow(
            """
            select coalesce(u.ui_locale, os.ui_locale, 'de') as locale
            from public.meetings m
            join public.users u on u.id = m.created_by
            left join public.org_settings os on os.org_id = m.org_id
            where m.id = $1
            """,
            meeting_id,
        )
        summary_locale = (locale_row and locale_row["locale"]) or "de"
        template = await conn.fetchrow(
            """
            select t.id, t.version, t.output_schema,
                   t.system_prompt          as t_system_prompt,
                   t.system_prompts         as t_system_prompts,
                   c.system_prompt          as c_system_prompt,
                   c.system_prompts         as c_system_prompts,
                   t.few_shot_input,
                   t.few_shot_output,
                   c.custom_fields,
                   (c.template_id is not null) as is_customized
            from public.templates t
            left join public.template_customizations c
                on c.template_id = t.id and c.org_id = $2
            where t.id = $1
            """,
            template_id,
            meeting["org_id"],
        )
        if not template:
            return {"status": "skipped", "reason": "template missing"}
        if template["is_customized"]:
            log.info("using org-customized system prompt for template %s", template_id)

        resolved_prompt = _resolve_prompt(template, summary_locale)
        if resolved_prompt is None:
            return {"status": "skipped", "reason": "template has no prompt"}
        template = {**dict(template), "system_prompt": resolved_prompt}
        log.info(
            "summarize: template=%s locale=%s (resolved from system_prompts)",
            template_id, summary_locale,
        )

        # Per-org LLM endpoint/key/model (falls back to env defaults).
        llm = await load_llm_config(conn, meeting["org_id"])

        await _set_status(conn, meeting_id, "summarizing")
    finally:
        await conn.close()

    # Wenn das Transkript Sprecher-Labels hat, geben wir der LLM eine
    # speaker-annotierte Version statt nackten Fließtext — damit kann sie
    # Beschlüsse Personen zuordnen. Ohne Labels: identisch zu vorher.
    transcript_for_llm = _format_transcript_for_llm(
        raw_segments,
        speakers_enriched,
        fallback=meeting["full_text"],
        locale=summary_locale,
    )

    payload = build_llm_payload(
        template=dict(template),
        speakers=speakers_enriched,
        transcript_for_llm=transcript_for_llm,
        model=llm.model,
        locale=summary_locale,
    )

    log.info(
        "summarize meeting %s · model=%s · template=%s",
        meeting_id, llm.model, template_id,
    )

    started = asyncio.get_event_loop().time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 10)) as client:
        resp = await client.post(
            f"{llm.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {llm.api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
    elapsed_ms = int((asyncio.get_event_loop().time() - started) * 1000)

    choices = data.get("choices") or []
    content = (choices[0].get("message", {}) or {}).get("content", "") if choices else ""
    if not content.strip():
        raise RuntimeError("LLM returned empty content")

    try:
        structured = json.loads(content)
    except json.JSONDecodeError as exc:
        log.error("ollama returned non-JSON content: %r", content[:500])
        raise RuntimeError(f"ollama returned non-JSON: {exc}") from exc

    conn = await _connect()
    try:
        async with conn.transaction():
            # Older summaries lose their current flag.
            await conn.execute(
                "update public.summaries set is_current = false where meeting_id = $1",
                meeting_id,
            )
            await conn.execute(
                """
                insert into public.summaries (
                    meeting_id, template_id, template_version,
                    content, llm_model, generation_time_ms, is_current
                )
                values ($1, $2, $3, $4::jsonb, $5, $6, true)
                """,
                meeting_id,
                template["id"],
                template["version"],
                json.dumps(structured),
                llm.model,
                elapsed_ms,
            )
            await _set_status(conn, meeting_id, "ready")
    finally:
        await conn.close()

    # Fan out the embedding job. Status stays "ready" — embedding is a
    # background nice-to-have for RAG; it doesn't gate the user's view.
    from app.worker import celery_app as _app
    _app.send_task("embed_meeting", args=[str(meeting_id)])

    # Notify subscribers (Duo, OpenWebUI, …) that the meeting is ready.
    _app.send_task("notify_webhook", args=[str(meeting_id), "meeting.ready"])

    return {
        "status": "ok",
        "elapsed_ms": elapsed_ms,
        "model": llm.model,
    }


@shared_task(
    name="summarize_meeting",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
)
def summarize_meeting(self, meeting_id: str) -> dict[str, Any]:  # noqa: ARG001
    mid = UUID(meeting_id)
    try:
        return asyncio.run(_do_summarize(mid))
    except Exception as exc:
        log.exception("summarize_meeting failed for %s", meeting_id)
        err_msg = f"summarize: {exc}"
        try:
            async def _mark_failed() -> None:
                conn = await _connect()
                try:
                    await _set_status(conn, mid, "failed", err_msg)
                finally:
                    await conn.close()

            asyncio.run(_mark_failed())
            from app.worker import celery_app as _app
            _app.send_task("notify_webhook", args=[meeting_id, "meeting.failed"])
        except Exception:
            log.exception("could not flag meeting %s as failed", meeting_id)
        raise
