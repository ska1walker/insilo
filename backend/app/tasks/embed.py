"""Celery task: chunk a transcript and write BGE-M3 embeddings to pgvector."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from celery import shared_task

from app.config import settings
from app.worker import celery_app  # noqa: F401 — side-effect: registers task

log = logging.getLogger(__name__)


# Rough chunking: BGE-M3 takes up to 8192 tokens but quality is best around
# 400-800. We split on whitespace into ~500-word chunks with a small overlap.
CHUNK_WORDS = 500
OVERLAP_WORDS = 60


async def _connect() -> asyncpg.Connection:
    return await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )


def _chunk_text(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(words):
        end = min(i + CHUNK_WORDS, len(words))
        chunks.append(" ".join(words[i:end]))
        if end == len(words):
            break
        i = end - OVERLAP_WORDS
    return chunks


def _to_pgvector(vec: list[float]) -> str:
    """pgvector accepts a string like '[0.1,0.2,...]' for the vector type."""
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def _embed_texts(texts: list[str]) -> tuple[list[list[float]], int]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 5)) as client:
        resp = await client.post(
            f"{settings.embeddings_url}/embed",
            json={"texts": texts, "normalize": True},
        )
        resp.raise_for_status()
        data = resp.json()
    return data["vectors"], int(data["dim"])


async def _do_embed(meeting_id: UUID) -> dict[str, Any]:
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            """
            select t.full_text
            from public.transcripts t
            join public.meetings m on m.id = t.meeting_id
            where m.id = $1 and m.deleted_at is null
            """,
            meeting_id,
        )
        if not row or not row["full_text"]:
            return {"status": "skipped", "reason": "no transcript"}

        full_text = row["full_text"]
        chunks = _chunk_text(full_text)
        if not chunks:
            return {"status": "skipped", "reason": "empty after chunking"}

        # Clear any previous chunks so re-embedding is idempotent.
        await conn.execute(
            "delete from public.meeting_chunks where meeting_id = $1", meeting_id
        )
    finally:
        await conn.close()

    log.info("embedding meeting %s · %d chunks", meeting_id, len(chunks))
    vectors, dim = await _embed_texts(chunks)
    if dim != 1024:
        log.warning("embedding dim mismatch: expected 1024 got %d", dim)

    # Word-position estimates so the chunk's relative spot in the meeting is
    # easy to reason about. Audio timestamps would require segment alignment
    # (Phase 2b); skipping for now.
    word_offsets: list[int] = []
    acc = 0
    for c in chunks:
        word_offsets.append(acc)
        acc += len(c.split()) - OVERLAP_WORDS  # advances by stride

    conn = await _connect()
    try:
        async with conn.transaction():
            for i, (chunk_text, vec) in enumerate(zip(chunks, vectors, strict=True)):
                await conn.execute(
                    """
                    insert into public.meeting_chunks (
                        meeting_id, chunk_index, content,
                        start_time_sec, end_time_sec, speaker_ids,
                        embedding, token_count
                    )
                    values ($1, $2, $3, null, null, null, $4::vector, $5)
                    """,
                    meeting_id,
                    i,
                    chunk_text,
                    _to_pgvector(vec),
                    len(chunk_text.split()),
                )
    finally:
        await conn.close()

    return {"status": "ok", "chunks": len(chunks), "dim": dim}


@shared_task(
    name="embed_meeting",
    bind=True,
    max_retries=1,
    default_retry_delay=15,
)
def embed_meeting(self, meeting_id: str) -> dict[str, Any]:  # noqa: ARG001
    mid = UUID(meeting_id)
    try:
        return asyncio.run(_do_embed(mid))
    except Exception:
        log.exception("embed_meeting failed for %s", meeting_id)
        # Do NOT flip the meeting to failed — embeddings are a nice-to-have
        # for RAG; the meeting is still usable without them. Just log.
        raise
