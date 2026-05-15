"""Speaker-Diarization für Insilo (Phase A, 3-Stage-Pipeline).

Nimmt Whisper-Segmente mit Timestamps + die Audio-Datei und gibt die
Segmente mit `speaker = "SPEAKER_00" | "SPEAKER_01" | …` zurück. Reine
anonyme Labels — die Zuordnung zu echten Namen erledigt Phase B
(Voice-Fingerprinting) bzw. der User manuell im Frontend.

Pipeline (token-frei, alle Modelle aus öffentlichen Repos):
1. **Silero-VAD** prüft pro Whisper-Segment, ob es überhaupt
   verwertbares Sprachsignal enthält (Schutz vor Phantom-Segmenten
   bei Husten/Rascheln). Trim auf den tatsächlich aktiven Sprach-
   Anteil, ehe das Embedding gezogen wird.
2. **SpeechBrain ECAPA-TDNN** wandelt jeden geprüften Chunk in ein
   192-dim L2-normalisiertes Sprecher-Embedding.
3. **sklearn AgglomerativeClustering** mit Cosinus-Linkage gruppiert
   die Embeddings; **Silhouette-Score** über k = 2..6 entscheidet,
   wie viele Sprecher tatsächlich da waren.

Sehr kurze (<0.5 s) oder von Silero als „kein Sprachsignal"
markierte Segmente erben das Label ihres Vorgängers, damit die
Transkript-Zeile nie ohne Sprecher dasteht.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import torch
from faster_whisper.audio import decode_audio
from silero_vad import get_speech_timestamps, load_silero_vad
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from speechbrain.inference.speaker import EncoderClassifier

log = logging.getLogger(__name__)

# 16 kHz mono ist der Standard für ECAPA-TDNN und Silero
TARGET_SR = 16_000
# Segmente kürzer als das sind zu wenig für ein stabiles Embedding
MIN_CHUNK_SEC = 0.5
# Maximal versuchte Sprecher-Anzahl im Silhouette-Vergleich
MAX_SPEAKERS = 6
# Wenn der beste Silhouette-Score darunter liegt: vermutlich nur 1 Sprecher
SINGLE_SPEAKER_THRESHOLD = 0.10
# Silero-VAD: Segment hat zu wenig Sprache, wenn aktiver Anteil < Schwelle
MIN_VOICE_RATIO = 0.30


@dataclass
class DiarizedSegment:
    start: float
    end: float
    speaker: str | None


@dataclass
class EmbeddingResult:
    """Result of a one-shot voice-enrollment embedding."""

    embedding: list[float]            # 192 floats, L2-normalised
    voiced_seconds: float             # active speech duration after VAD
    total_seconds: float              # raw audio duration as decoded


_embedder: EncoderClassifier | None = None
_vad_model = None  # silero-vad: pytorch jit-Modell


def load_embedder(cache_dir: str) -> EncoderClassifier:
    """Eager-load das ECAPA-Modell. Erst-Aufruf zieht ~60 MB Gewichte."""
    global _embedder
    if _embedder is None:
        log.info("loading speaker-embedder spkrec-ecapa-voxceleb (cache=%s)", cache_dir)
        _embedder = EncoderClassifier.from_hparams(
            source="speechbrain/spkrec-ecapa-voxceleb",
            savedir=cache_dir,
            run_opts={"device": "cpu"},
        )
        log.info("speaker-embedder loaded")
    return _embedder


def load_vad():
    """Eager-load das Silero-VAD-Modell. Bundle ~2 MB JIT-Tensor."""
    global _vad_model
    if _vad_model is None:
        log.info("loading silero-vad")
        _vad_model = load_silero_vad()
        log.info("silero-vad loaded")
    return _vad_model


def _vad_trim(chunk: np.ndarray) -> np.ndarray | None:
    """Silero-VAD: behalte nur die tatsächlich gesprochenen Anteile.

    Returns:
        Voice-gestripptes Audio, oder None falls weniger als MIN_VOICE_RATIO
        des Chunks tatsächlich Stimme ist (= „kein verwertbares Signal").
    """
    if _vad_model is None:
        return chunk  # VAD nicht verfügbar → vertraue Whisper-Boundary

    chunk_tensor = torch.from_numpy(chunk).float()
    try:
        speech_ts = get_speech_timestamps(
            chunk_tensor,
            _vad_model,
            sampling_rate=TARGET_SR,
            threshold=0.5,
            min_silence_duration_ms=200,
            min_speech_duration_ms=150,
        )
    except Exception as exc:
        log.warning("silero-vad failed for chunk: %s", exc)
        return chunk

    if not speech_ts:
        return None

    voiced_samples = sum(t["end"] - t["start"] for t in speech_ts)
    if voiced_samples < len(chunk) * MIN_VOICE_RATIO:
        return None

    # Stitch nur die voiced-Intervalle zusammen — Embedding wird sauberer
    voiced_audio = np.concatenate(
        [chunk[t["start"]:t["end"]] for t in speech_ts]
    )
    return voiced_audio


def _embed_chunk(audio_16k: np.ndarray, start_sec: float, end_sec: float) -> np.ndarray | None:
    """Extrahiert das ECAPA-Embedding für einen Audio-Ausschnitt.

    Stufe 1: Silero-VAD trimmt auf die tatsächlich gesprochenen Anteile.
    Stufe 2: ECAPA-TDNN liefert das 192-dim Sprecher-Embedding.
    """
    embedder = _embedder
    if embedder is None:
        return None

    start_sample = int(start_sec * TARGET_SR)
    end_sample = int(end_sec * TARGET_SR)
    chunk = audio_16k[start_sample:end_sample]
    if len(chunk) < TARGET_SR * MIN_CHUNK_SEC:
        return None

    # Stufe 1 — VAD-Filter
    voiced = _vad_trim(chunk.astype(np.float32))
    if voiced is None or len(voiced) < TARGET_SR * MIN_CHUNK_SEC:
        return None

    # Stufe 2 — ECAPA-Embedding
    tensor = torch.from_numpy(voiced).float().unsqueeze(0)
    with torch.no_grad():
        emb = embedder.encode_batch(tensor).squeeze().cpu().numpy()
    # ECAPA gibt einen L2-normalisierten Vektor zurück; sicher ist sicher
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm
    return emb


def _estimate_speakers(embeddings: np.ndarray) -> tuple[int, np.ndarray]:
    """Bester k im Bereich 2..MAX_SPEAKERS via Silhouette-Score.

    Returns (n_speakers, labels). Bei nur einem klaren Cluster → (1, all-zeros).
    """
    if len(embeddings) < 2:
        return 1, np.zeros(len(embeddings), dtype=int)

    best_k = 1
    best_score = -1.0
    best_labels: np.ndarray | None = None

    max_k = min(MAX_SPEAKERS, len(embeddings))
    for k in range(2, max_k + 1):
        clustering = AgglomerativeClustering(
            n_clusters=k,
            metric="cosine",
            linkage="average",
        ).fit(embeddings)
        labels = clustering.labels_
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(embeddings, labels, metric="cosine")
        if score > best_score:
            best_score = score
            best_k = k
            best_labels = labels

    if best_labels is None or best_score < SINGLE_SPEAKER_THRESHOLD:
        return 1, np.zeros(len(embeddings), dtype=int)
    return best_k, best_labels


@dataclass
class DiarizationResult:
    """Result of one diarization run.

    Backwards-compat: `speaker_labels` is what v0.1.31..36 returned. The
    new fields (`cluster_indices`, `cluster_centroids`) feed the
    org-speaker matching pipeline introduced in v0.1.37.
    """

    speaker_labels: list[str | None]            # "SPEAKER_00", … (one per segment)
    cluster_indices: list[int | None]           # 0,1,2,… (one per segment) or None
    cluster_centroids: list[list[float]]        # N × 192 floats, L2-normalised


def embed_voice_sample(
    audio_path: str,
    *,
    min_voiced_seconds: float = 3.0,
) -> EmbeddingResult | None:
    """One-shot voice enrollment: load audio, VAD-trim, ECAPA-embed.

    Returns None if either of:
      - the embedder isn't loaded
      - the audio file can't be decoded
      - the VAD finds fewer than `min_voiced_seconds` of active speech

    The result's `embedding` is L2-normalised and directly comparable to
    `cluster_centroids[i]` from `diarize()` (same model, same norm).
    """
    if _embedder is None:
        log.warning("embed_voice_sample() called before load_embedder()")
        return None

    audio_16k = decode_audio(audio_path, sampling_rate=TARGET_SR).astype(np.float32)
    total_seconds = float(len(audio_16k) / TARGET_SR)

    # VAD trim — speakers reading the Nordwind passage typically have
    # ~30 s clean speech, but we cap nothing here. The embedder is happy
    # with up to ~60 s; longer just gets truncated by ECAPA naturally.
    voiced = _vad_trim(audio_16k)
    if voiced is None:
        log.info("voice enrollment: no usable speech detected (total=%.1fs)", total_seconds)
        return None

    voiced_seconds = float(len(voiced) / TARGET_SR)
    if voiced_seconds < min_voiced_seconds:
        log.info(
            "voice enrollment: only %.1fs voiced (< %.1fs minimum)",
            voiced_seconds, min_voiced_seconds,
        )
        return None

    tensor = torch.from_numpy(voiced).float().unsqueeze(0)
    with torch.no_grad():
        emb = _embedder.encode_batch(tensor).squeeze().cpu().numpy()
    norm = np.linalg.norm(emb)
    if norm > 0:
        emb = emb / norm

    return EmbeddingResult(
        embedding=emb.astype(float).tolist(),
        voiced_seconds=voiced_seconds,
        total_seconds=total_seconds,
    )


def diarize(
    audio_path: str,
    segments: list[tuple[float, float]],
) -> DiarizationResult:
    """Diarize the segments of a single audio file.

    Args:
        audio_path: Pfad zur Audio-Datei (faster-whisper-temp).
        segments: Liste von (start_sec, end_sec) — die Whisper-Output-Segmente.

    Returns:
        DiarizationResult mit per-Segment-Labels + per-Segment-Cluster-Index
        + per-Cluster-Centroid. Der Centroid ist der L2-normalisierte
        Mittelwert aller ECAPA-Embeddings dieses Clusters und dient als
        "Voice-Fingerprint" für das Org-Speaker-Matching im Backend.
    """
    if not segments:
        return DiarizationResult([], [], [])
    if _embedder is None:
        log.warning("diarize() called before load_embedder() — skipping")
        return DiarizationResult([None] * len(segments), [None] * len(segments), [])

    # Audio laden + auf 16 kHz mono bringen (decode_audio macht beides via ffmpeg)
    audio_16k = decode_audio(audio_path, sampling_rate=TARGET_SR)

    # Embeddings pro Segment
    embeddings: list[np.ndarray | None] = [
        _embed_chunk(audio_16k, s, e) for (s, e) in segments
    ]
    valid_idx = [i for i, emb in enumerate(embeddings) if emb is not None]
    if len(valid_idx) < 2:
        # Zu wenige verwertbare Chunks — alles zu Sprecher 0 zusammenfassen.
        # Centroid berechnen wir trotzdem (falls eines da war) — der Org-
        # Matcher kann auch mit einem einzelnen Sprecher arbeiten.
        if valid_idx:
            single = embeddings[valid_idx[0]]
            norm = np.linalg.norm(single)
            centroid = (single / norm).tolist() if norm > 0 else single.tolist()
            centroids: list[list[float]] = [centroid]
        else:
            centroids = []
        return DiarizationResult(
            speaker_labels=["SPEAKER_00"] * len(segments),
            cluster_indices=[0] * len(segments),
            cluster_centroids=centroids,
        )

    valid_array = np.stack([embeddings[i] for i in valid_idx])
    n_speakers, labels = _estimate_speakers(valid_array)
    log.info(
        "diarization: %d Segmente · %d Sprecher erkannt", len(segments), n_speakers
    )

    # Centroids pro Cluster: L2-normalisierter Mittelwert der Cluster-
    # Mitglieder. Aktuelles Cluster-Set = unique(labels), sortiert.
    cluster_ids = sorted({int(label) for label in labels})
    centroids = []
    for cid in cluster_ids:
        members = valid_array[labels == cid]
        mean = members.mean(axis=0)
        norm = np.linalg.norm(mean)
        if norm > 0:
            mean = mean / norm
        centroids.append(mean.astype(float).tolist())

    # Label-Liste + Cluster-Index-Liste füllen, zu kurze Segmente vom
    # Vorgänger erben lassen.
    speaker_labels: list[str | None] = [None] * len(segments)
    cluster_indices: list[int | None] = [None] * len(segments)
    for cluster_label, seg_idx in zip(labels, valid_idx, strict=False):
        cl = int(cluster_label)
        speaker_labels[seg_idx] = f"SPEAKER_{cl:02d}"
        cluster_indices[seg_idx] = cl

    last_label: str | None = None
    last_cluster: int | None = None
    for i in range(len(segments)):
        if speaker_labels[i] is None:
            speaker_labels[i] = last_label or "SPEAKER_00"
            cluster_indices[i] = last_cluster if last_cluster is not None else 0
        else:
            last_label = speaker_labels[i]
            last_cluster = cluster_indices[i]

    return DiarizationResult(
        speaker_labels=speaker_labels,
        cluster_indices=cluster_indices,
        cluster_centroids=centroids,
    )
