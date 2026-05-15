"""Cluster-Centroid → Org-Speaker matching via cosine similarity.

The whisper-service hands us L2-normalised 192-d centroids for every
cluster it found in a meeting. We compare them against every org-speaker
whose stored voiceprint is non-null, and assign the closest match if
the similarity is above the configured threshold.

Math: with L2-normalised vectors, cosine similarity == dot product.
So similarity = centroids @ voiceprints.T (a small dense matmul).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
import numpy as np

from app.config import settings


@dataclass(frozen=True)
class MatchResult:
    """Best-match outcome for one cluster-centroid."""

    org_speaker_id: UUID | None
    display_name: str | None
    score: float                  # best cosine similarity (raw, may be <threshold)
    is_self: bool = False


def _to_pgvector(vec: list[float]) -> str:
    """asyncpg → pgvector accepts the string form '[v1,v2,…]' for $1::vector."""
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def _parse_pgvector(text: str) -> np.ndarray:
    """pgvector returns the vector as a string like '[v1,v2,…]'."""
    return np.fromstring(text.strip("[]"), sep=",", dtype=np.float32)


def _normalize(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v)
    if norm == 0:
        return v
    return v / norm


async def load_org_voiceprints(
    conn: asyncpg.Connection, org_id: UUID
) -> tuple[list[dict[str, Any]], np.ndarray | None]:
    """Fetch every speaker in the org that has a non-null voiceprint.

    Returns (rows, matrix) where matrix is (S, 192) of stacked voiceprints
    in the same order as rows. Returns ([], None) if the org has no
    voiceprinted speakers yet.
    """
    rows = await conn.fetch(
        """
        select id, display_name, is_self, voiceprint::text as voiceprint_txt
        from public.org_speakers
        where org_id = $1 and voiceprint is not null
        """,
        org_id,
    )
    if not rows:
        return [], None
    matrix = np.stack([_parse_pgvector(r["voiceprint_txt"]) for r in rows])
    return [dict(r) for r in rows], matrix


def match_centroids(
    centroids: list[list[float]],
    voiceprint_rows: list[dict[str, Any]],
    voiceprint_matrix: np.ndarray | None,
    threshold: float | None = None,
) -> list[MatchResult]:
    """Match each centroid to the closest voiceprint above threshold.

    Pure function — no DB calls. The caller passes the org_speaker rows
    + the pre-loaded voiceprint matrix.
    """
    if threshold is None:
        threshold = settings.speaker_match_threshold

    if not voiceprint_rows or voiceprint_matrix is None or not centroids:
        return [MatchResult(None, None, 0.0, False) for _ in centroids]

    cc = np.stack([np.asarray(c, dtype=np.float32) for c in centroids])  # (C, 192)
    sim = cc @ voiceprint_matrix.T                                       # (C, S)

    results: list[MatchResult] = []
    for c_idx in range(cc.shape[0]):
        best_s_idx = int(sim[c_idx].argmax())
        best_score = float(sim[c_idx, best_s_idx])
        if best_score >= threshold:
            row = voiceprint_rows[best_s_idx]
            results.append(
                MatchResult(
                    org_speaker_id=row["id"],
                    display_name=row["display_name"],
                    score=best_score,
                    is_self=bool(row.get("is_self", False)),
                )
            )
        else:
            results.append(MatchResult(None, None, best_score, False))
    return results


async def append_voiceprint_sample(
    conn: asyncpg.Connection,
    *,
    org_speaker_id: UUID,
    meeting_id: UUID,
    cluster_idx: int,
    embedding: list[float],
    source: str,
    created_by: UUID | None = None,
) -> None:
    """Append a new voiceprint sample and recompute the speaker's primary
    voiceprint as the L2-normalised mean of the most-recent N samples.

    Uses `speaker_max_voiceprints_per_speaker` to cap how many samples
    feed into the mean (FIFO — older samples get dropped from the
    averaging window, but stay in the audit log).
    """
    embedding_arr = _normalize(np.asarray(embedding, dtype=np.float32))
    cap = settings.speaker_max_voiceprints_per_speaker

    async with conn.transaction():
        await conn.execute(
            """
            insert into public.speaker_voiceprints (
                org_speaker_id, meeting_id, cluster_idx, embedding,
                source, created_by
            ) values ($1, $2, $3, $4::vector, $5, $6)
            """,
            org_speaker_id,
            meeting_id,
            cluster_idx,
            _to_pgvector(embedding_arr.tolist()),
            source,
            created_by,
        )

        # Window: most recent <cap> samples.
        recent = await conn.fetch(
            """
            select embedding::text as emb
            from public.speaker_voiceprints
            where org_speaker_id = $1
            order by created_at desc
            limit $2
            """,
            org_speaker_id,
            cap,
        )
        if not recent:
            return
        samples = np.stack([_parse_pgvector(r["emb"]) for r in recent])
        mean = _normalize(samples.mean(axis=0))

        # Atomic update of speaker stats.
        total_count = await conn.fetchval(
            "select count(*) from public.speaker_voiceprints where org_speaker_id = $1",
            org_speaker_id,
        )
        await conn.execute(
            """
            update public.org_speakers
            set voiceprint = $2::vector,
                sample_count = $3,
                last_heard_at = now()
            where id = $1
            """,
            org_speaker_id,
            _to_pgvector(mean.tolist()),
            int(total_count or 0),
        )


__all__ = [
    "MatchResult",
    "load_org_voiceprints",
    "match_centroids",
    "append_voiceprint_sample",
    "_to_pgvector",
    "_parse_pgvector",
]
