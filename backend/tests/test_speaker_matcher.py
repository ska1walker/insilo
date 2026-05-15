"""Tests for the speaker cluster→org-speaker matcher.

The matching logic itself is a pure dense matmul, so we can test it
without a database. We construct synthetic L2-normalised vectors that
either match closely or are orthogonal.
"""

from __future__ import annotations

from uuid import uuid4

import numpy as np
import pytest

from app.speaker_matcher import (
    MatchResult,
    _parse_pgvector,
    _to_pgvector,
    match_centroids,
)


def _unit(seed: int, dim: int = 192) -> list[float]:
    """Reproducible L2-normalised random vector."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dim).astype(np.float32)
    v /= np.linalg.norm(v)
    return v.tolist()


def _perturbed(base: list[float], strength: float = 0.1, seed: int = 0) -> list[float]:
    """Return a vector close to `base`, still L2-normalised."""
    rng = np.random.default_rng(seed)
    arr = np.asarray(base, dtype=np.float32)
    noise = rng.standard_normal(arr.shape).astype(np.float32)
    noise /= np.linalg.norm(noise)
    out = arr + strength * noise
    out /= np.linalg.norm(out)
    return out.tolist()


def test_match_centroids_returns_neutral_when_no_voiceprints():
    centroids = [_unit(1), _unit(2)]
    results = match_centroids(centroids, voiceprint_rows=[], voiceprint_matrix=None)
    assert len(results) == 2
    assert all(r.org_speaker_id is None for r in results)
    assert all(r.score == 0.0 for r in results)


def test_match_centroids_matches_close_voiceprint():
    # Speaker A's canonical voiceprint, and one slightly perturbed
    # version that represents the current meeting's cluster.
    voiceprint_a = _unit(seed=42)
    cluster_a = _perturbed(voiceprint_a, strength=0.05, seed=7)
    cluster_b_unrelated = _unit(seed=999)

    rows = [
        {"id": uuid4(), "display_name": "Kai", "is_self": True, "voiceprint_txt": ""},
    ]
    matrix = np.array([voiceprint_a], dtype=np.float32)

    results = match_centroids(
        [cluster_a, cluster_b_unrelated],
        voiceprint_rows=rows,
        voiceprint_matrix=matrix,
        threshold=0.5,
    )

    # Perturbed copy should match.
    assert results[0].org_speaker_id == rows[0]["id"]
    assert results[0].display_name == "Kai"
    assert results[0].is_self is True
    assert results[0].score > 0.9, results[0].score

    # Orthogonal random vector should NOT match.
    assert results[1].org_speaker_id is None
    assert results[1].score < 0.5


def test_match_centroids_picks_closest_of_many():
    # Three speakers; one of them is a near-twin of our cluster.
    vp1 = _unit(seed=10)
    vp2 = _unit(seed=20)
    vp3 = _unit(seed=30)
    cluster = _perturbed(vp2, strength=0.03, seed=5)

    ids = [uuid4(), uuid4(), uuid4()]
    rows = [
        {"id": ids[0], "display_name": "A", "is_self": False, "voiceprint_txt": ""},
        {"id": ids[1], "display_name": "B", "is_self": False, "voiceprint_txt": ""},
        {"id": ids[2], "display_name": "C", "is_self": False, "voiceprint_txt": ""},
    ]
    matrix = np.array([vp1, vp2, vp3], dtype=np.float32)

    results = match_centroids([cluster], rows, matrix, threshold=0.5)
    assert results[0].org_speaker_id == ids[1]
    assert results[0].display_name == "B"


def test_match_centroids_respects_threshold():
    # Generate a moderately similar pair; with strict threshold no match,
    # with permissive threshold it matches.
    vp = _unit(seed=11)
    cluster = _perturbed(vp, strength=0.9, seed=2)  # noisy

    rows = [{"id": uuid4(), "display_name": "X", "is_self": False, "voiceprint_txt": ""}]
    matrix = np.array([vp], dtype=np.float32)

    strict = match_centroids([cluster], rows, matrix, threshold=0.95)
    permissive = match_centroids([cluster], rows, matrix, threshold=0.05)

    assert strict[0].org_speaker_id is None
    assert permissive[0].org_speaker_id == rows[0]["id"]


def test_pgvector_roundtrip():
    """Serialise / parse keeps the vector intact (up to float precision)."""
    original = _unit(seed=99)
    txt = _to_pgvector(original)
    assert txt.startswith("[") and txt.endswith("]")
    parsed = _parse_pgvector(txt)
    assert parsed.shape == (192,)
    # Allow for fp32 → text → fp32 round-trip with the 7-digit format.
    assert np.allclose(parsed, original, atol=1e-6)


@pytest.mark.parametrize("n_clusters", [1, 3, 6])
def test_empty_voiceprints_returns_per_cluster_neutral(n_clusters: int):
    centroids = [_unit(seed=i) for i in range(n_clusters)]
    results = match_centroids(centroids, [], None)
    assert len(results) == n_clusters
    assert all(isinstance(r, MatchResult) for r in results)
    assert all(r.org_speaker_id is None for r in results)
