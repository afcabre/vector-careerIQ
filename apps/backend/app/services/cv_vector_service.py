from hashlib import sha1
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import Settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - fallback path when package is missing.
    OpenAI = None  # type: ignore[assignment]


CHUNK_SIZE = 900
CHUNK_OVERLAP = 180
MAX_CHUNKS = 120


def _is_ready(settings: Settings) -> bool:
    return bool(
        settings.openai_api_key
        and settings.openai_embedding_model
        and settings.pinecone_api_key
        and settings.pinecone_index_host
    )


def _chunk_text(raw_text: str) -> list[str]:
    text = raw_text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    step = max(1, CHUNK_SIZE - CHUNK_OVERLAP)
    while start < len(text) and len(chunks) < MAX_CHUNKS:
        chunk = text[start : start + CHUNK_SIZE].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def _embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    if not texts or OpenAI is None:
        return []
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.embeddings.create(
        model=settings.openai_embedding_model,
        input=texts,
    )
    vectors = [item.embedding for item in response.data]
    return [list(vector) for vector in vectors]


def _pinecone_url(settings: Settings, path: str) -> str:
    host = settings.pinecone_index_host.strip()
    if not host:
        return ""
    if host.startswith("http://") or host.startswith("https://"):
        base = host
    else:
        base = f"https://{host}"
    return f"{base.rstrip('/')}{path}"


def _pinecone_post(
    settings: Settings,
    path: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    request = Request(
        url=_pinecone_url(settings, path),
        method="POST",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Api-Key": settings.pinecone_api_key,
        },
    )
    with urlopen(request, timeout=25) as response:
        raw = response.read().decode("utf-8")
    parsed = json.loads(raw) if raw else {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def upsert_cv_vectors(
    record: dict[str, Any],
    settings: Settings,
) -> tuple[str, int]:
    if not _is_ready(settings):
        return "skipped_missing_vector_config", 0

    text = str(record.get("extracted_text", "")).strip()
    chunks = _chunk_text(text)
    if not chunks:
        return "skipped_empty_cv_text", 0

    try:
        embeddings = _embed_texts(chunks, settings)
    except Exception:
        return "failed_embedding", 0
    if not embeddings or len(embeddings) != len(chunks):
        return "failed_embedding_shape", 0

    person_id = str(record.get("person_id", "")).strip()
    cv_id = str(record.get("cv_id", "")).strip()
    vectors: list[dict[str, Any]] = []
    for index, (chunk, values) in enumerate(zip(chunks, embeddings, strict=False)):
        digest = sha1(f"{cv_id}:{index}".encode("utf-8")).hexdigest()[:12]
        vectors.append(
            {
                "id": f"cv-{cv_id}-{digest}",
                "values": values,
                "metadata": {
                    "person_id": person_id,
                    "cv_id": cv_id,
                    "chunk_index": index,
                    "text": chunk,
                },
            }
        )

    try:
        _pinecone_post(
            settings,
            "/vectors/upsert",
            {
                "namespace": person_id,
                "vectors": vectors,
            },
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return "failed_pinecone_upsert", 0
    except Exception:
        return "failed_pinecone_upsert", 0

    return "indexed", len(vectors)


def query_cv_context(
    person_id: str,
    cv_id: str,
    query_text: str,
    settings: Settings,
    top_k: int = 4,
) -> list[str]:
    if not _is_ready(settings):
        return []
    query_text = query_text.strip()
    if not query_text:
        return []

    try:
        embedded = _embed_texts([query_text], settings)
    except Exception:
        return []
    if not embedded:
        return []

    try:
        response = _pinecone_post(
            settings,
            "/query",
            {
                "namespace": person_id,
                "vector": embedded[0],
                "topK": top_k,
                "includeMetadata": True,
                "filter": {"cv_id": {"$eq": cv_id}},
            },
        )
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
        return []
    except Exception:
        return []

    snippets: list[str] = []
    for match in response.get("matches", []):
        metadata = match.get("metadata", {})
        if not isinstance(metadata, dict):
            continue
        text = str(metadata.get("text", "")).strip()
        if text:
            snippets.append(text)
    return snippets
