"""
Embedding helper — generates vector embeddings via Gemini embedding model.
Used for semantic search in the knowledge base (pgvector).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 3072


async def generate_embedding(text: str) -> list[float]:
    """Generate a 3072-dim embedding for a text string using Gemini."""
    from app.llm.gemini_client import get_client

    client = get_client()
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text[:2000],  # Truncate to avoid token limits
    )
    return response.embeddings[0].values


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    results = []
    for text in texts:
        try:
            emb = await generate_embedding(text)
            results.append(emb)
        except Exception as e:
            logger.warning(f"[embeddings] Failed for text '{text[:50]}...': {e}")
            results.append([0.0] * EMBEDDING_DIM)
    return results
