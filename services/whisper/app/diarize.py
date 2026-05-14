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
import soundfile as sf
import torch
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


def _resample_if_needed(audio: np.ndarray, sr: int) -> np.ndarray:
    """Sicherstellen, dass ECAPA seine 16 kHz bekommt."""
    if sr == TARGET_SR:
        return audio.astype(np.float32)
    # Lazy import — librosa ist nur fürs Resampling nötig
    import librosa
    return librosa.resample(audio.astype(np.float32), orig_sr=sr, target_sr=TARGET_SR)


def _to_mono(audio: np.ndarray) -> np.ndarray:
    if audio.ndim == 1:
        return audio
    return audio.mean(axis=1)


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


def diarize(
    audio_path: str,
    segments: list[tuple[float, float]],
) -> list[str | None]:
    """Diarize the segments of a single audio file.

    Args:
        audio_path: Pfad zur Audio-Datei (faster-whisper-temp).
        segments: Liste von (start_sec, end_sec) — die Whisper-Output-Segmente.

    Returns:
        Liste von Speaker-Labels (`"SPEAKER_00"` etc.) in derselben
        Reihenfolge wie `segments`. None nur wenn ein Segment komplett zu
        kurz war und kein Nachbar einsprang (sollte selten passieren).
    """
    if not segments:
        return []
    if _embedder is None:
        log.warning("diarize() called before load_embedder() — skipping")
        return [None] * len(segments)

    # Audio laden + auf 16 kHz mono bringen
    audio, sr = sf.read(audio_path, always_2d=False)
    audio = _to_mono(audio)
    audio_16k = _resample_if_needed(audio, sr)

    # Embeddings pro Segment
    embeddings: list[np.ndarray | None] = [
        _embed_chunk(audio_16k, s, e) for (s, e) in segments
    ]
    valid_idx = [i for i, emb in enumerate(embeddings) if emb is not None]
    if len(valid_idx) < 2:
        # Zu wenige verwertbare Chunks — alles zu Sprecher 0 zusammenfassen
        return ["SPEAKER_00"] * len(segments)

    valid_array = np.stack([embeddings[i] for i in valid_idx])
    n_speakers, labels = _estimate_speakers(valid_array)
    log.info(
        "diarization: %d Segmente · %d Sprecher erkannt", len(segments), n_speakers
    )

    # Result-Liste füllen + zu kurze Segmente vom Vorgänger erben lassen
    result: list[str | None] = [None] * len(segments)
    for cluster_label, seg_idx in zip(labels, valid_idx, strict=False):
        result[seg_idx] = f"SPEAKER_{int(cluster_label):02d}"

    last_seen: str | None = None
    for i in range(len(result)):
        if result[i] is None:
            result[i] = last_seen or "SPEAKER_00"
        else:
            last_seen = result[i]

    return result
