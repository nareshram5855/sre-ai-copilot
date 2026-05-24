"""
Document ingestion pipeline.

Flow: filesystem docs → chunk → embed (nomic-embed-text) → ChromaDB

Design decisions:
- Chunk size 512 tokens: empirically best for SRE docs (runbooks have short
  numbered steps; smaller chunks preserve step boundaries better than 1k+).
- 64-token overlap: prevents a fix command from being split mid-sentence.
- Graceful fallback to PersistentClient when ChromaDB is unreachable.
"""
import logging
from pathlib import Path

import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.document_loaders import TextLoader

from backend.config import settings
from backend.rag.embeddings import get_embeddings

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


def _get_chroma_client() -> chromadb.ClientAPI:
    """Return HTTP client if ChromaDB is reachable, otherwise PersistentClient."""
    try:
        client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
        client.heartbeat()
        logger.info("Connected to ChromaDB via HTTP")
        return client
    except Exception:
        fallback_path = Path(__file__).parent.parent.parent / ".chroma_data"
        fallback_path.mkdir(exist_ok=True)
        logger.warning("ChromaDB HTTP unavailable — using PersistentClient at %s", fallback_path)
        return chromadb.PersistentClient(path=str(fallback_path))


def _load_documents(directory: Path) -> list:
    """Recursively load all .md and .txt files from a directory."""
    docs = []
    for ext in ("*.md", "*.txt"):
        for file_path in directory.rglob(ext):
            try:
                loader = TextLoader(str(file_path), encoding="utf-8")
                docs.extend(loader.load())
            except Exception as e:
                logger.warning("Failed to load %s: %s", file_path, e)
    return docs


def ingest_directory(collection_name: str, subdirectory: str) -> int:
    """Ingest a knowledge base subdirectory into a ChromaDB collection."""
    target_dir = KNOWLEDGE_DIR / subdirectory

    if not target_dir.exists() or not any(target_dir.rglob("*.md")):
        logger.warning("No documents found in %s", target_dir)
        return 0

    documents = _load_documents(target_dir)
    if not documents:
        return 0

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=64,
        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_documents(documents)
    logger.info("Split %d docs into %d chunks for '%s'", len(documents), len(chunks), collection_name)

    chroma_client = _get_chroma_client()

    # Delete existing collection so re-ingestion is idempotent
    try:
        chroma_client.delete_collection(collection_name)
    except Exception:
        pass

    Chroma.from_documents(
        documents=chunks,
        embedding=get_embeddings(),
        collection_name=collection_name,
        client=chroma_client,
    )

    logger.info("Ingested %d chunks into '%s'", len(chunks), collection_name)
    return len(chunks)


def ingest_text(
    collection_name: str,
    text: str,
    metadata: dict | None = None,
    *,
    doc_id: str | None = None,
) -> bool:
    """Add a single document to an existing ChromaDB collection."""
    from langchain_core.documents import Document

    if not text.strip():
        return False

    try:
        chroma_client = _get_chroma_client()
        store = Chroma(
            collection_name=collection_name,
            embedding_function=get_embeddings(),
            client=chroma_client,
        )
        doc = Document(page_content=text, metadata=metadata or {})
        ids = [doc_id] if doc_id else None
        store.add_documents([doc], ids=ids)
        logger.info("Ingested 1 document into '%s' (id=%s)", collection_name, doc_id)
        return True
    except Exception as exc:
        logger.warning("Single-document ingest failed for '%s': %s", collection_name, exc)
        return False


def ingest_all() -> dict[str, int]:
    """Ingest all registered knowledge domains. Safe to call repeatedly.
    Domains are driven by config.knowledge_collections — adding a new domain
    requires only a config entry and a new knowledge/ subdirectory."""
    results = {}
    for domain, collection_name in settings.knowledge_collections.items():
        results[domain] = ingest_directory(collection_name, domain)
    return results
