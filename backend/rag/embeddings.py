from langchain_ollama import OllamaEmbeddings
from backend.config import settings


def get_embeddings() -> OllamaEmbeddings:
    # nomic-embed-text produces 768-dim vectors and runs in ~200ms on M-series.
    # Much faster than sentence-transformers for local dev since it reuses the
    # same Ollama process already serving the LLM.
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )
