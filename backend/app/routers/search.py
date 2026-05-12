"""Semantic search + RAG over the org's meeting transcripts.

Two endpoints:
  - POST /api/v1/search  → top-k chunks for a query (no LLM)
  - POST /api/v1/ask     → grounded answer with cited source chunks
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import CurrentUser, get_current_user
from app.config import settings
from app.db import acquire

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["search"])


# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)
    limit: int = Field(default=10, ge=1, le=50)


class SearchHit(BaseModel):
    meeting_id: str
    meeting_title: str
    meeting_date: str
    chunk_index: int
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHit]


class AskRequest(BaseModel):
    question: str = Field(..., min_length=4, max_length=500)
    limit: int = Field(default=6, ge=1, le=20)


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[SearchHit]
    llm_model: str
    elapsed_ms: int


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _to_pgvector(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


async def _embed_query(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
        resp = await client.post(
            f"{settings.embeddings_url}/embed",
            json={"texts": [text], "normalize": True},
        )
        resp.raise_for_status()
        data = resp.json()
    return data["vectors"][0]


async def _retrieve(
    org_id, query_vec: list[float], limit: int
) -> list[SearchHit]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            select c.meeting_id, c.chunk_index, c.content,
                   m.title, m.recorded_at,
                   (c.embedding <=> $1::vector) as distance
            from public.meeting_chunks c
            join public.meetings m on m.id = c.meeting_id
            where m.org_id = $2 and m.deleted_at is null
            order by c.embedding <=> $1::vector
            limit $3
            """,
            _to_pgvector(query_vec),
            org_id,
            limit,
        )
    return [
        SearchHit(
            meeting_id=str(r["meeting_id"]),
            meeting_title=r["title"],
            meeting_date=r["recorded_at"].isoformat(),
            chunk_index=r["chunk_index"],
            content=r["content"],
            # Cosine distance is in [0, 2]; convert to similarity in [-1, 1].
            score=float(1.0 - r["distance"]),
        )
        for r in rows
    ]


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------

@router.post("/search", response_model=SearchResponse)
async def search(
    req: SearchRequest, user: CurrentUser = Depends(get_current_user)
) -> SearchResponse:
    try:
        qvec = await _embed_query(req.query)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"embeddings service unreachable: {exc}") from exc

    hits = await _retrieve(user.org_id, qvec, req.limit)
    return SearchResponse(query=req.query, hits=hits)


def _build_rag_prompt(question: str, hits: list[SearchHit]) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)."""
    system = (
        "Du bist der Wissensassistent für Insilo, eine Meeting-Intelligenz-Plattform. "
        "Beantworte die Frage des Nutzers AUSSCHLIESSLICH auf Basis der unten gelieferten "
        "Auszüge aus früheren Besprechungs-Transkripten der Organisation. "
        "Wenn die Auszüge keine ausreichende Antwort hergeben, sage es ehrlich — "
        "erfinde nichts. Antworte auf Deutsch, sachlich, ohne Marketing-Sprech. "
        "Zitiere Quellen über die mitgegebenen Marker [#1], [#2] usw. im Fließtext."
    )

    excerpts = []
    for i, h in enumerate(hits, start=1):
        excerpts.append(
            f"[#{i}] Besprechung „{h.meeting_title}“ ({h.meeting_date[:10]}), "
            f"Abschnitt {h.chunk_index + 1}:\n{h.content}\n"
        )
    excerpts_block = "\n".join(excerpts) if excerpts else "(keine relevanten Auszüge gefunden)"

    user = (
        "=== AUSZÜGE AUS MEETING-TRANSKRIPTEN ===\n"
        f"{excerpts_block}\n"
        "=== ENDE AUSZÜGE ===\n\n"
        f"Frage: {question}\n\n"
        "Antworte direkt und knapp, mit Quell-Markern wo passend."
    )
    return system, user


@router.post("/ask", response_model=AskResponse)
async def ask(
    req: AskRequest, user: CurrentUser = Depends(get_current_user)
) -> AskResponse:
    import asyncio as _asyncio

    started = _asyncio.get_event_loop().time()

    try:
        qvec = await _embed_query(req.question)
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"embeddings service unreachable: {exc}") from exc

    hits = await _retrieve(user.org_id, qvec, req.limit)

    system_prompt, user_prompt = _build_rag_prompt(req.question, hits)

    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60 * 5)) as client:
            resp = await client.post(f"{settings.ollama_url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(503, f"LLM unreachable: {exc}") from exc

    answer = (data.get("message") or {}).get("content") or ""
    elapsed_ms = int((_asyncio.get_event_loop().time() - started) * 1000)

    return AskResponse(
        question=req.question,
        answer=answer.strip(),
        sources=hits,
        llm_model=settings.ollama_model,
        elapsed_ms=elapsed_ms,
    )
