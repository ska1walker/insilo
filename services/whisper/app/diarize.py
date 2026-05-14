"""Speaker-Diarization für Insilo (Phase A).

Nimmt Whisper-Segmente mit Timestamps + die Audio-Datei und gibt die
Segmente mit `speaker = "SPEAKER_00" | "SPEAKER_01" | …` zurück. Reine
anonyme Labels — die Zuordnung zu echten Namen erledigt Phase B
(Voice-Fingerprinting) bzw. der User manuell im Frontend.

Pipeline:
1. Pro Whisper-Segment ein Audio-Chunk schneiden
2. SpeechBrain ECAPA-TDNN extrahiert ein 192-dim Embedding pro Chunk
3. AgglomerativeClustering mit Cosinus-Distanz gruppiert ähnliche
   Embeddings → das ist die Sprecher-Zugehörigkeit
4. Sprecher-Count via Silhouette-Score über k = 2..6 geschätzt
5. Sehr kurze (<0.5s) oder leere Chunks erben das Label des Vorgängers

Kein HuggingFace-Token nötig — SpeechBrain-Modelle laden ohne Auth aus
ihrem öffentlichen Repo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import soundfile as sf
import torch
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from speechbrain.inference.speaker import EncoderClassifier

log = logging.getLogger(__name__)

# 16 kHz mono ist der Standard für ECAPA-TDNN
TARGET_SR = 16_000
# Segmente kürzer als das sind zu wenig für ein stabiles Embedding
MIN_CHUNK_SEC = 0.5
# Maximal versuchte Sprecher-Anzahl im Silhouette-Vergleich
MAX_SPEAKERS = 6
# Wenn der beste Silhouette-Score darunter liegt: vermutlich nur 1 Sprecher
SINGLE_SPEAKER_THRESHOLD = 0.10


@dataclass
class DiarizedSegment:
    start: float
    end: float
    speaker: str | None


_embedder: EncoderClassifier | None = None


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


def _embed_chunk(audio_16k: np.ndarray, start_sec: float, end_sec: float) -> np.ndarray | None:
    """Extrahiert das ECAPA-Embedding für einen Audio-Ausschnitt."""
    embedder = _embedder
    if embedder is None:
        return None

    start_sample = int(start_sec * TARGET_SR)
    end_sample = int(end_sec * TARGET_SR)
    chunk = audio_16k[start_sample:end_sample]
    if len(chunk) < TARGET_SR * MIN_CHUNK_SEC:
        return None

    tensor = torch.from_numpy(chunk).float().unsqueeze(0)
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
