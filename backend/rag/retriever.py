import logging
from pathlib import Path

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document

from backend.config import settings
from backend.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)


def _get_chroma_client() -> chromadb.ClientAPI:
    try:
        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        client.heartbeat()
        return client
    except Exception:
        fallback_path = Path(__file__).parent.parent.parent / ".chroma_data"
        return chromadb.PersistentClient(path=str(fallback_path))


def _get_store(collection_name: str) -> Chroma:
    return Chroma(
        collection_name=collection_name,
        embedding_function=get_embeddings(),
        client=_get_chroma_client(),
    )


def retrieve_similar(query: str, collection_name: str, k: int = 4) -> list[Document]:
    """Return k most similar documents for a query."""
    try:
        store = _get_store(collection_name)
        return store.similarity_search(query, k=k)
    except Exception as e:
        logger.warning("Retrieval failed for '%s': %s", collection_name, e)
        return []


def retrieve_with_score(
    query: str, collection_name: str, k: int = 4
) -> list[tuple[Document, float]]:
    """Return documents paired with their L2 distance scores (lower = more similar)."""
    try:
        store = _get_store(collection_name)
        return store.similarity_search_with_score(query, k=k)
    except Exception as e:
        logger.warning("Scored retrieval failed for '%s': %s", collection_name, e)
        return []
