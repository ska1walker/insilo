"""Celery task: transcribe an uploaded meeting via the Whisper service."""

from __future__ import annotations

import asyncio
import json
import logging
import math
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
import httpx
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from starlette.concurrency import run_in_threadpool

from app import ablage, audiostuecke
from app.audioformat import audio_endung
from app.config import settings
from app.db import dienst_kontext
from app.speaker_matcher import (
    _to_pgvector,
    append_voiceprint_sample,
    load_org_voiceprints,
    match_centroids,
)
from app.storage import get_bytes as _storage_get_bytes
from app.stt_config import STTConfig, load_stt_config
from app.verarbeitungszeit import hartes_limit, stt_zeitlimit, weiches_limit
from app.worker import celery_app  # noqa: F401  -- import side-effect: registers

log = logging.getLogger(__name__)


async def _set_status(
    conn: asyncpg.Connection, meeting_id: UUID, status: str, error: str | None = None
) -> None:
    await conn.execute(
        """
        update public.meetings
        set status = $2,
            error_message = $3,
            updated_at = now()
        where id = $1
        """,
        meeting_id,
        status,
        error,
    )


async def _connect() -> asyncpg.Connection:
    """Eigene Verbindung für diese Aufgabe — mit Dienst-Kontext.

    Hintergrundaufgaben haben keinen angemeldeten Nutzer. Unter der
    erzwungenen Zeilensicherheit aus Migration 0017 sähen sie ohne
    Kontext keine Zeile und könnten keine schreiben.
    """
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )
    await dienst_kontext(conn)
    return conn


@dataclass(frozen=True)
class Transkript:
    """Was ein Transkriptionsweg liefert — egal welcher.

    Beide Wege füllen dieselben Felder, damit der Rest der Pipeline nicht
    wissen muss, wer transkribiert hat.
    """

    segments: list[dict[str, Any]]
    full_text: str
    cluster_centroids: list[list[float]]
    language: str | None
    model: str
    duration: float | None
    # Woher der Text kommt — landet im Audit-Log und im Datenschutz-Nachweis.
    quelle: str  # "lokal" | "extern"


def _host_kurz(url: str) -> str:
    """Nur der Rechnername, für Meldungen an den Nutzer."""
    return urlsplit(url).hostname or url


def _dateiname(mime: str) -> str:
    """Dateiname mit passender Endung für den Upload.

    Einige STT-Server erkennen das Format an der Endung, nicht am
    MIME-Typ — mit "recording.bin" laufen sie ins Leere.
    """
    return f"recording.{audio_endung(mime)}"


def _dauer_sekunden(
    dauer: float | None, segmente: list[dict[str, Any]] | None = None,
) -> int | None:
    """Die gemessene Dauer als ganze Sekunden, oder `None`, wenn es keine gibt.

    Die Spracherkennung kennt die echte Länge. Gespeichert war bisher nur,
    was der Browser behauptete — bei einer hochgeladenen Datei, deren Länge
    der Browser nicht auslesen kann, eine Sekunde. Nennt ein fremder Dienst
    keine Dauer, ist das Ende des letzten Segments die beste Schätzung.
    """
    if dauer is None or not math.isfinite(dauer) or dauer <= 0:
        enden = [float(s.get("end") or 0.0) for s in (segmente or [])]
        dauer = max(enden, default=0.0)
    if not math.isfinite(dauer) or dauer <= 0:
        return None
    return max(1, round(dauer))


async def _transkribieren_lokal(
    audio_bytes: bytes, mime: str, language: str | None, zeitlimit: float,
    diarisieren: bool = True,
) -> Transkript:
    """Der mitgelieferte Whisper-Dienst. Text und Sprecher in einem Aufruf.

    `language` wird weggelassen statt auf None gesetzt, damit
    faster-whisper selbst erkennt (sein Vorgabewert).

    `zeitlimit` hängt an der Länge der Aufnahme — warum, steht in
    `app/verarbeitungszeit.py`. Dieser Weg ist der langsame: ohne GPU
    braucht er mehr Rechenzeit, als die Aufnahme lang ist.

    `diarisieren=False` für einen einzelnen Abschnitt einer langen
    Aufnahme: die Sprecher werden dann einmal am Ende über die ganze
    Datei getrennt, nicht je Abschnitt (siehe `app/audiostuecke.py`).
    """
    form_data: dict[str, str] = {"diarisieren": "true" if diarisieren else "false"}
    if language:
        form_data["language"] = language
    async with httpx.AsyncClient(timeout=httpx.Timeout(zeitlimit)) as client:
        resp = await client.post(
            f"{settings.whisper_url}/transcribe",
            files={"audio": ("recording.bin", audio_bytes, mime)},
            data=form_data,
        )
        resp.raise_for_status()
        result = resp.json()
    return Transkript(
        segments=result["segments"],
        full_text=result["full_text"],
        cluster_centroids=result.get("cluster_centroids") or [],
        language=result.get("language"),
        model=result.get("model") or "unknown",
        duration=result.get("duration"),
        quelle="lokal",
    )


async def _transkribieren_extern(
    audio_bytes: bytes, mime: str, language: str | None, stt: STTConfig,
    zeitlimit: float, diarisieren: bool = True,
) -> Transkript:
    """Externer OpenAI-kompatibler STT-Server, Sprecher weiterhin lokal.

    `response_format=verbose_json` liefert Segmente mit Zeiten; ohne sie
    gäbe es nur einen Textblock, und die Sprechertrennung hätte keine
    Grenzen, an denen sie ansetzen könnte. Antwortet der Endpunkt nur mit
    Text, arbeiten wir mit einem einzigen Segment weiter — lieber ein
    Transkript ohne Sprecher als gar keins.
    """
    # Die Modellkennung ist bei OpenAI-kompatiblen Endpunkten ein
    # Pflichtfeld — Speaches etwa antwortet ohne sie mit 422 und
    # "model: Field required". Das hier abzufangen ist ehrlicher, als den
    # Endpunkt einen Formfehler melden zu lassen: es fehlt eine Angabe,
    # der Dienst ist nicht kaputt.
    if not stt.model:
        raise RuntimeError(
            "Für die Spracherkennung fehlt die Modell-ID. Der eingetragene "
            f"Endpunkt ({_host_kurz(stt.base_url)}) verlangt sie bei jeder "
            "Anfrage. Sie steht unter Einstellungen › Spracherkennung; "
            "welche Kennungen der Endpunkt kennt, verrät sein /v1/models."
        )

    daten: dict[str, str] = {
        "response_format": "verbose_json",
        "model": stt.model,
    }
    if language:
        daten["language"] = language

    async with httpx.AsyncClient(timeout=httpx.Timeout(zeitlimit)) as client:
        resp = await client.post(
            f"{stt.base_url}/audio/transcriptions",
            # Dateiname mit echter Endung: manche Server leiten das Format
            # daraus ab statt aus dem MIME-Typ.
            files={"file": (_dateiname(mime), audio_bytes, mime)},
            data=daten,
            headers=stt.auth_header,
        )
        if resp.status_code >= 400:
            # Den Antwortkörper mitgeben. `raise_for_status()` allein
            # liefert nur "422 Unprocessable Entity", und der Nutzer steht
            # vor einer Sackgasse — dabei steht der Grund im Körper.
            raise RuntimeError(
                f"Der Spracherkennungs-Dienst antwortete mit HTTP "
                f"{resp.status_code}: {resp.text[:400]}"
            )
        roh = resp.json()

    volltext = (roh.get("text") or "").strip()
    segmente: list[dict[str, Any]] = [
        {
            "start": float(s.get("start", 0.0)),
            "end": float(s.get("end", 0.0)),
            "text": (s.get("text") or "").strip(),
            "speaker": None,
            "cluster_idx": None,
        }
        for s in (roh.get("segments") or [])
        if (s.get("text") or "").strip()
    ]
    if not segmente and volltext:
        dauer = float(roh.get("duration") or 0.0)
        segmente = [{
            "start": 0.0, "end": dauer, "text": volltext,
            "speaker": None, "cluster_idx": None,
        }]
    if not volltext:
        volltext = " ".join(s["text"] for s in segmente).strip()

    # Bei einem einzelnen Abschnitt einer langen Aufnahme nicht: die
    # Sprechertrennung clustert Stimmen gegeneinander und muss die ganze
    # Datei sehen. Je Abschnitt aufgerufen wäre sie nicht nur verschwendet,
    # sondern falsch — dieselbe Person bekäme in jedem Abschnitt eine
    # eigene Nummer.
    centroids = (
        await _sprecher_ergaenzen(audio_bytes, mime, segmente, zeitlimit)
        if diarisieren
        else []
    )
    return Transkript(
        segments=segmente,
        full_text=volltext,
        cluster_centroids=centroids,
        language=roh.get("language") or language,
        model=stt.model or "extern",
        duration=float(roh["duration"]) if roh.get("duration") is not None else None,
        quelle="extern",
    )


async def _sprecher_ergaenzen(
    audio_bytes: bytes, mime: str, segmente: list[dict[str, Any]],
    zeitlimit: float,
) -> list[list[float]]:
    """Sprecher zu fremd erzeugten Segmenten, über den lokalen Dienst.

    Schlägt das fehl, bleibt es beim Transkript ohne Sprechernamen — das
    ist ein Verlust an Komfort, kein Grund, die Besprechung scheitern zu
    lassen. Genau deshalb hing hier ein fester Riegel von zehn Minuten:
    er fiel bei langen Aufnahmen still, und niemand sah, warum die
    Sprechernamen fehlten. Er hängt jetzt an derselben Rechnung wie die
    Erkennung.
    """
    if not segmente:
        return []
    grenzen = json.dumps([[s["start"], s["end"]] for s in segmente])
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(zeitlimit)) as client:
            resp = await client.post(
                f"{settings.whisper_url}/diarize",
                files={"audio": ("recording.bin", audio_bytes, mime)},
                data={"segments": grenzen},
            )
            resp.raise_for_status()
            d = resp.json()
    except Exception as exc:  # noqa: BLE001
        log.warning("speaker separation unavailable, continuing without: %s", exc)
        return []

    for seg, sprecher, cidx in zip(
        segmente, d.get("speakers") or [], d.get("cluster_indices") or [],
        strict=False,
    ):
        seg["speaker"] = sprecher
        seg["cluster_idx"] = cidx
    return d.get("cluster_centroids") or []


def _fehlertext(exc: BaseException) -> str:
    """Der Satz, der in der Oberfläche unter der Besprechung steht.

    Für die meisten Fehler ist die Ausnahme selbst schon aussagekräftig
    (die Meldungen in diesem Modul sind dafür geschrieben). Für die zwei
    Zeitriegel ist sie es nicht: `SoftTimeLimitExceeded(14100,)` sagt
    niemandem, was zu tun ist — dabei ist gerade hier klar, was hilft.
    """
    if isinstance(exc, SoftTimeLimitExceeded | httpx.TimeoutException):
        minuten = round(hartes_limit() / 60)
        return (
            "Die Verarbeitung hat länger gedauert als erlaubt "
            f"({minuten} Minuten) und wurde abgebrochen. Die Aufnahme "
            "selbst liegt unversehrt auf der Box. Bei langen Aufnahmen "
            "liegt das fast immer am Erkennungsmodell: ohne Grafikkarte "
            "braucht der mitgelieferte Dienst mehr Rechenzeit, als die "
            "Aufnahme lang ist. Unter Einstellungen › Spracherkennung "
            "lässt sich ein schnellerer Endpunkt eintragen; danach die "
            "Verarbeitung erneut anstoßen."
        )
    return str(exc)


async def _fortschritt(meeting_id: UUID, fertig: int, gesamt: int) -> None:
    """Wie weit die Erkennung ist, für die Oberfläche.

    `updated_at` geht mit: davon hängt ab, ob der Wächter die Besprechung
    für abgestürzt hält (`app/tasks/waechter.py`). Eine Aufnahme, die
    stundenlang Abschnitt für Abschnitt abarbeitet, meldet sich damit
    regelmäßig als lebendig.
    """
    conn = await _connect()
    try:
        await conn.execute(
            """
            update public.meetings
            set metadata = coalesce(metadata, '{}'::jsonb)
                || jsonb_build_object('fortschritt',
                     jsonb_build_object('fertig', $2::int, 'gesamt', $3::int)),
                updated_at = now()
            where id = $1
            """,
            meeting_id, fertig, gesamt,
        )
    finally:
        await conn.close()


async def _fertige_abschnitte(
    meeting_id: UUID, teile: list[audiostuecke.Abschnitt],
) -> dict[int, dict[str, Any]]:
    """Was ein früherer Versuch schon erkannt hat.

    Nur, was zur *jetzigen* Aufteilung passt. Ändert sich die
    Abschnittslänge zwischen zwei Versuchen (jemand stellt
    `INSILO_STUECK_SEKUNDEN` um), zeigt Abschnitt 3 auf eine andere Stelle
    der Aufnahme als beim letzten Mal — und der alte Wortlaut säße dann an
    der falschen Zeit im Transkript.
    """
    conn = await _connect()
    try:
        zeilen = await conn.fetch(
            """
            select idx, start_sec, end_sec, segments, text, language
            from public.transcription_chunks
            where meeting_id = $1
            order by idx
            """,
            meeting_id,
        )
    finally:
        await conn.close()

    nach_index = {t.index: t for t in teile}
    passend: dict[int, dict[str, Any]] = {}
    for z in zeilen:
        teil = nach_index.get(z["idx"])
        if teil is None or abs(teil.start - z["start_sec"]) > 0.5 \
                or abs(teil.ende - z["end_sec"]) > 0.5:
            continue
        rohe = z["segments"]
        passend[z["idx"]] = {
            "segments": json.loads(rohe) if isinstance(rohe, str) else rohe,
            "text": z["text"],
            "language": z["language"],
        }
    return passend


async def _abschnitt_ablegen(
    meeting_id: UUID, teil: audiostuecke.Abschnitt, ergebnis: dict[str, Any],
) -> None:
    conn = await _connect()
    try:
        await conn.execute(
            """
            insert into public.transcription_chunks
                (meeting_id, idx, start_sec, end_sec, segments, text, language)
            values ($1, $2, $3, $4, $5::jsonb, $6, $7)
            on conflict (meeting_id, idx) do update
            set segments = excluded.segments,
                text = excluded.text,
                language = excluded.language,
                created_at = now()
            """,
            meeting_id, teil.index, teil.start, teil.ende,
            json.dumps(ergebnis["segments"]), ergebnis["text"], ergebnis["language"],
        )
    finally:
        await conn.close()


async def _abschnitte_verwerfen(conn: asyncpg.Connection, meeting_id: UUID) -> None:
    """Der Zwischenstand, sobald das fertige Transkript steht.

    Zwei Quellen für denselben Wortlaut wären eine zu viel.
    """
    await conn.execute(
        "delete from public.transcription_chunks where meeting_id = $1", meeting_id
    )


async def _erkennen(
    inhalt: bytes, mime: str, language: str | None, stt: STTConfig, zeitlimit: float,
) -> Transkript:
    """Ein Stück Ton zu Text — über den Weg, der eingerichtet ist.

    Ohne Sprechertrennung: die läuft einmal am Ende über die ganze Datei.
    """
    if stt.eingerichtet:
        return await _transkribieren_extern(
            inhalt, mime, language, stt, zeitlimit, diarisieren=False
        )
    return await _transkribieren_lokal(
        inhalt, mime, language, zeitlimit, diarisieren=False
    )


async def _stueckweise(
    meeting_id: UUID, audio_bytes: bytes, mime: str, language: str | None,
    stt: STTConfig, zeitlimit_gesamt: float,
) -> Transkript | None:
    """Eine lange Aufnahme abschnittsweise erkennen, oder `None`.

    `None` heißt „zu kurz, ffmpeg fehlt, oder es ließ sich nicht sinnvoll
    teilen" — dann nimmt der Aufrufer den Weg mit einem Aufruf, also das
    Verhalten bis 0.1.98. Das ist wichtig: ein fehlendes ffmpeg soll ein
    Rückschritt sein, kein Ausfall.

    Die Sprechertrennung kommt am Ende über die **ganze** Datei. Je
    Abschnitt zu clustern hieße, dass derselbe Mensch in Abschnitt drei
    anders heißt als in Abschnitt eins.
    """
    # Nicht in `/tmp`: das wäre auf der Box der flüchtige Speicher des
    # Knotens, und eine große Aufnahme könnte den Pod verdrängen lassen.
    with tempfile.TemporaryDirectory(
        prefix="insilo-stuecke-", dir=audiostuecke.arbeitsordner()
    ) as ordner:
        arbeitsordner = Path(ordner)
        quelle = arbeitsordner / f"aufnahme.{audio_endung(mime)}"
        quelle.write_bytes(audio_bytes)

        teile = await run_in_threadpool(audiostuecke.aufteilen, quelle)
        if not teile:
            return None

        schon_da = await _fertige_abschnitte(meeting_id, teile)
        if schon_da:
            log.info(
                "meeting %s: %d von %d Abschnitten lagen schon vor",
                meeting_id, len(schon_da), len(teile),
            )
        await _fortschritt(meeting_id, len(schon_da), len(teile))

        ergebnisse: dict[int, dict[str, Any]] = dict(schon_da)
        for teil in teile:
            if teil.index in ergebnisse:
                continue
            ziel = arbeitsordner / f"teil-{teil.index:03d}.ogg"
            if not await run_in_threadpool(audiostuecke.schneiden, quelle, teil, ziel):
                # Ein Abschnitt, der sich nicht schneiden lässt, ist ein
                # Grund, den ganzen Weg zu verwerfen — ein Transkript mit
                # einem stillschweigend fehlenden Stück wäre schlimmer als
                # ein langsamer Durchlauf am Stück.
                log.warning("meeting %s: Abschnitt %d misslungen, ganze Datei am Stück",
                            meeting_id, teil.index)
                return None

            inhalt = ziel.read_bytes()
            tr = await _erkennen(
                inhalt, audiostuecke.MEDIENTYP_STUECK, language, stt,
                stt_zeitlimit(round(teil.dauer), len(inhalt)),
            )
            ergebnisse[teil.index] = {
                "segments": audiostuecke.versetzen(tr.segments, teil.start),
                "text": tr.full_text,
                "language": tr.language,
            }
            await _abschnitt_ablegen(meeting_id, teil, ergebnisse[teil.index])
            await _fortschritt(meeting_id, len(ergebnisse), len(teile))
            log.info(
                "meeting %s: Abschnitt %d von %d erkannt (%.0f–%.0fs)",
                meeting_id, teil.index + 1, len(teile), teil.start, teil.ende,
            )

        segmente: list[dict[str, Any]] = []
        texte: list[str] = []
        for teil in teile:
            e = ergebnisse[teil.index]
            segmente.extend(e["segments"])
            if e["text"]:
                texte.append(e["text"])

        # Einmal über alles: nur so sind die Sprechernamen durchgehend
        # dieselben. `_sprecher_ergaenzen` setzt `speaker`/`cluster_idx`
        # an den Segmenten selbst.
        centroids = await _sprecher_ergaenzen(
            audio_bytes, mime, segmente, zeitlimit_gesamt
        )

    sprachen = [e["language"] for e in ergebnisse.values() if e["language"]]
    return Transkript(
        segments=segmente,
        full_text=" ".join(texte).strip(),
        cluster_centroids=centroids,
        # Die erste erkannte Sprache gilt: eine Besprechung wechselt sie
        # nicht, und ein einzelner Abschnitt kann sich verschätzen.
        language=sprachen[0] if sprachen else language,
        model="stückweise",
        duration=teile[-1].ende,
        quelle="extern" if stt.eingerichtet else "lokal",
    )


async def _do_transcribe(meeting_id: UUID) -> dict[str, Any]:
    """The real work — split out so we can run it inside asyncio.run()."""
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            """
            select audio_path, org_id, language, duration_sec,
                   metadata->>'mime_type' as mime
            from public.meetings
            where id = $1
            """,
            meeting_id,
        )
        if not row or not row["audio_path"]:
            return {"status": "skipped", "reason": "no audio_path"}
        org_id = row["org_id"]

        await _set_status(conn, meeting_id, "transcribing")
    finally:
        await conn.close()

    # Pull audio out of storage (MinIO or local FS depending on backend).
    # Either path is sync; the bytes are small enough that blocking the event
    # loop briefly is fine.
    audio_bytes = _storage_get_bytes(row["audio_path"])
    mime = row["mime"] or "audio/webm"
    requested_language = row["language"]  # NULL = auto-detect (caller's choice)
    zeitlimit = stt_zeitlimit(row["duration_sec"], len(audio_bytes))
    log.info(
        "transcribing meeting %s (%d bytes, %s, language=%s, limit=%ds)",
        meeting_id, len(audio_bytes), mime, requested_language or "auto",
        round(zeitlimit),
    )

    # Zwei Wege, je nach Einrichtung: der mitgelieferte Dienst im eigenen
    # Namespace (Vorgabe, kein Audio verlässt die Box) oder ein
    # eingetragener OpenAI-kompatibler STT-Server. Beim zweiten Weg holen
    # wir den Text von dort und die Sprecher weiterhin hier — ein
    # OpenAI-STT kennt keine Sprecher.
    conn = await _connect()
    try:
        stt = await load_stt_config(conn, org_id)
    finally:
        await conn.close()

    # Lange Aufnahmen gehen abschnittsweise durch (`app/audiostuecke.py`):
    # kein einzelner Aufruf läuft mehr in ein Zeitlimit, die Oberfläche
    # kann den Fortschritt zeigen, und ein Abbruch kostet nur den einen
    # Abschnitt. Ist die Aufnahme kurz oder fehlt ffmpeg, bleibt es beim
    # einen Aufruf wie bisher.
    tr = await _stueckweise(
        meeting_id, audio_bytes, mime, requested_language, stt, zeitlimit
    )
    if tr is None:
        if stt.eingerichtet:
            log.info("transcribing via external endpoint %s", stt.base_url)
            tr = await _transkribieren_extern(
                audio_bytes, mime, requested_language, stt, zeitlimit
            )
        else:
            tr = await _transkribieren_lokal(
                audio_bytes, mime, requested_language, zeitlimit
            )

    segments = tr.segments
    full_text = tr.full_text
    cluster_centroids = tr.cluster_centroids

    # ─── Org-Speaker-Matching ─────────────────────────────────────────
    # Wenn die Org bereits Voiceprints kennt, ordnen wir jeden Cluster-
    # Centroid dem ähnlichsten Org-Speaker zu (cosine ≥ Threshold).
    # speakers_payload ist die Liste, die in transcripts.speakers landet —
    # mit echten Namen wo zugeordnet, sonst weiterhin "SPEAKER_NN".
    conn = await _connect()
    try:
        rows, vp_matrix = await load_org_voiceprints(conn, org_id)
    finally:
        await conn.close()
    matches = match_centroids(cluster_centroids, rows, vp_matrix) if cluster_centroids else []

    # Pro Cluster ein Speaker-Eintrag — id zeigt entweder auf einen Org-
    # Speaker ("org_<uuid>") oder bleibt cluster-anonym ("cluster_<n>").
    speakers_payload: list[dict[str, Any]] = []
    for c_idx in range(len(cluster_centroids)):
        if c_idx < len(matches) and matches[c_idx].org_speaker_id is not None:
            m = matches[c_idx]
            speakers_payload.append({
                "id": f"org_{m.org_speaker_id}",
                "name": m.display_name,
                "org_speaker_id": str(m.org_speaker_id),
                "match_score": round(m.score, 4),
                "assignment": "auto",
            })
        else:
            score = matches[c_idx].score if c_idx < len(matches) else 0.0
            speakers_payload.append({
                "id": f"cluster_{c_idx}",
                "name": f"SPEAKER_{c_idx:02d}",
                "match_score": round(score, 4),
                "assignment": "pending",
            })

    # Patch segment.speaker so the IDs in transcripts.segments line up
    # with the canonical speaker list above.
    for seg in segments:
        c_idx = seg.get("cluster_idx")
        if c_idx is not None and 0 <= c_idx < len(speakers_payload):
            seg["speaker"] = speakers_payload[c_idx]["id"]

    # ─── Persist transcript + clusters + auto-match voiceprints ──────
    conn = await _connect()
    try:
        async with conn.transaction():
            await conn.execute(
                """
                insert into public.transcripts (
                    meeting_id, segments, speakers, full_text,
                    language, whisper_model, word_count
                )
                values ($1, $2::jsonb, $3::jsonb, $4, $5, $6, $7)
                on conflict (meeting_id) do update set
                    segments = excluded.segments,
                    speakers = excluded.speakers,
                    full_text = excluded.full_text,
                    language = excluded.language,
                    whisper_model = excluded.whisper_model,
                    word_count = excluded.word_count
                """,
                meeting_id,
                json.dumps(segments),
                json.dumps(speakers_payload),
                full_text,
                tr.language or settings.app_lang,
                tr.model,
                len(full_text.split()),
            )

            # Wipe any clusters from a previous transcribe (re-diarize case),
            # then persist the new cluster set.
            await conn.execute(
                "delete from public.meeting_speaker_clusters where meeting_id = $1",
                meeting_id,
            )
            for c_idx, centroid in enumerate(cluster_centroids):
                match = matches[c_idx] if c_idx < len(matches) else None
                await conn.execute(
                    """
                    insert into public.meeting_speaker_clusters (
                        meeting_id, cluster_idx, centroid,
                        org_speaker_id, match_score, assignment
                    )
                    values ($1, $2, $3::vector, $4, $5, $6)
                    """,
                    meeting_id,
                    c_idx,
                    _to_pgvector(centroid),
                    match.org_speaker_id if match else None,
                    match.score if match else None,
                    "auto" if (match and match.org_speaker_id) else "pending",
                )

            sekunden = _dauer_sekunden(tr.duration, segments)
            if sekunden is not None:
                await conn.execute(
                    "update public.meetings set duration_sec = $2 where id = $1",
                    meeting_id,
                    sekunden,
                )

            # Der Wortlaut steht jetzt in `transcripts` — der Zwischenstand
            # der Abschnitte hat seinen Zweck erfüllt und geht mit dem
            # Fortschrittszähler zusammen weg.
            await _abschnitte_verwerfen(conn, meeting_id)
            await conn.execute(
                """
                update public.meetings
                set metadata = coalesce(metadata, '{}'::jsonb) - 'fortschritt'
                where id = $1
                """,
                meeting_id,
            )
            await _set_status(conn, meeting_id, "transcribed")

        # Feed auto-matched centroids back into the speakers' voiceprint
        # history — that's how voiceprints refine over time. We do this
        # outside the main transaction so a single bad sample doesn't
        # roll back the whole transcript.
        for c_idx, match in enumerate(matches):
            if match.org_speaker_id is None or c_idx >= len(cluster_centroids):
                continue
            try:
                await append_voiceprint_sample(
                    conn,
                    org_speaker_id=match.org_speaker_id,
                    meeting_id=meeting_id,
                    cluster_idx=c_idx,
                    embedding=cluster_centroids[c_idx],
                    source="auto-match",
                )
            except Exception:
                log.exception(
                    "auto-match voiceprint append failed for speaker %s",
                    match.org_speaker_id,
                )

        # Das Transkript neben die Aufnahme legen. Schon hier, nicht erst
        # nach der Zusammenfassung: ohne eingerichtetes Sprachmodell
        # kommt die nie, und der Wortlaut soll trotzdem als Datei
        # dastehen.
        await ablage.schreiben(conn, meeting_id)
    finally:
        await conn.close()

    # Hand off to the LLM summarizer. Use send_task to avoid a circular import.
    from app.worker import celery_app as _app
    _app.send_task("summarize_meeting", args=[str(meeting_id)])

    return {
        "status": "ok",
        "segments": len(segments),
        "language": tr.language,
        "duration": tr.duration,
    }


@shared_task(
    name="transcribe_meeting",
    bind=True,
    max_retries=2,
    default_retry_delay=10,
    # Eigene Limits statt der globalen aus `app.worker`. Die gelten für
    # jede Aufgabe gleich und sind für einen Webhook richtig bemessen —
    # für eine Stunde Audio auf der CPU nicht. Warum sie an der Länge der
    # Aufnahme hängen, steht in `app/verarbeitungszeit.py`.
    time_limit=hartes_limit(),
    soft_time_limit=weiches_limit(),
)
def transcribe_meeting(self, meeting_id: str) -> dict[str, Any]:  # noqa: ARG001 (bind=True)
    """Sync Celery wrapper. Drives the async pipeline via asyncio.run."""
    mid = UUID(meeting_id)
    try:
        return asyncio.run(_do_transcribe(mid))
    except Exception as exc:
        log.exception("transcribe_meeting failed for %s", meeting_id)
        # Best-effort: mark the meeting as failed so the UI can show it.
        err_msg = _fehlertext(exc)
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
