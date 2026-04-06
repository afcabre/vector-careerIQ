from hashlib import sha1
import logging
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.settings import Settings

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - fallback path when package is missing.
    OpenAI = None  # type: ignore[assignment]

try:
    import tiktoken
except ImportError:  # pragma: no cover - fallback when dependency is missing.
    tiktoken = None  # type: ignore[assignment]

CHUNK_TARGET_TOKENS = 700
CHUNK_OVERLAP_RATIO = 0.12
CHUNK_OVERLAP_TOKENS = int(CHUNK_TARGET_TOKENS * CHUNK_OVERLAP_RATIO)
CHUNK_STEP_TOKENS = CHUNK_TARGET_TOKENS - CHUNK_OVERLAP_TOKENS
CHAR_FALLBACK_PER_TOKEN = 4
CHUNK_TARGET_CHARS = CHUNK_TARGET_TOKENS * CHAR_FALLBACK_PER_TOKEN
CHUNK_OVERLAP_CHARS = CHUNK_OVERLAP_TOKENS * CHAR_FALLBACK_PER_TOKEN
MAX_CHUNKS = 120


def _is_ready(settings: Settings) -> bool:
    return bool(
        settings.openai_api_key
        and settings.openai_embedding_model
        and settings.pinecone_api_key
        and settings.pinecone_index_host
    )


def _token_encoder(settings: Settings):
    if tiktoken is None:
        return None
    try:
        return tiktoken.encoding_for_model(settings.openai_embedding_model)
    except Exception:
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception:
            return None


def _chunk_text_fallback(raw_text: str) -> list[str]:
    text = raw_text.strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    step = max(1, CHUNK_TARGET_CHARS - CHUNK_OVERLAP_CHARS)
    while start < len(text) and len(chunks) < MAX_CHUNKS:
        chunk = text[start : start + CHUNK_TARGET_CHARS].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def _chunk_text(raw_text: str, settings: Settings) -> list[str]:
    text = raw_text.strip()
    if not text:
        return []

    encoder = _token_encoder(settings)
    if encoder is None:
        return _chunk_text_fallback(text)

    token_ids = encoder.encode(text)
    if not token_ids:
        return []

    chunks: list[str] = []
    start = 0
    step = max(1, CHUNK_STEP_TOKENS)
    while start < len(token_ids) and len(chunks) < MAX_CHUNKS:
        chunk_ids = token_ids[start : start + CHUNK_TARGET_TOKENS]
        if not chunk_ids:
            break
        chunk = encoder.decode(chunk_ids).strip()
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
    person_id = str(record.get("person_id", "")).strip()
    cv_id = str(record.get("cv_id", "")).strip()

    if not _is_ready(settings):
        logger.warning(
            "vector upsert skipped due to missing config person_id=%s cv_id=%s",
            person_id,
            cv_id,
        )
        return "skipped_missing_vector_config", 0

    text = str(record.get("extracted_text", "")).strip()
    chunks = _chunk_text(text, settings)
    if not chunks:
        logger.warning(
            "vector upsert skipped due to empty text person_id=%s cv_id=%s",
            person_id,
            cv_id,
        )
        return "skipped_empty_cv_text", 0

    try:
        embeddings = _embed_texts(chunks, settings)
    except Exception:
        logger.exception(
            "embedding generation failed person_id=%s cv_id=%s", person_id, cv_id
        )
        return "failed_embedding", 0
    if not embeddings or len(embeddings) != len(chunks):
        logger.warning(
            "embedding shape mismatch person_id=%s cv_id=%s chunks=%s vectors=%s",
            person_id,
            cv_id,
            len(chunks),
            len(embeddings),
        )
        return "failed_embedding_shape", 0

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
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning(
            "pinecone upsert failed person_id=%s cv_id=%s error=%s",
            person_id,
            cv_id,
            exc,
        )
        return "failed_pinecone_upsert", 0
    except Exception:
        logger.exception("pinecone upsert unexpected error person_id=%s cv_id=%s", person_id, cv_id)
        return "failed_pinecone_upsert", 0

    return "indexed", len(vectors)


def query_cv_context(
    person_id: str,
    cv_id: str,
    query_text: str,
    settings: Settings,
    top_k: int = 24,
) -> list[str]:
    if not _is_ready(settings):
        logger.warning("semantic query skipped due to missing vector config person_id=%s", person_id)
        return []
    query_text = query_text.strip()
    if not query_text:
        logger.warning("semantic query skipped due to empty query person_id=%s cv_id=%s", person_id, cv_id)
        return []

    try:
        embedded = _embed_texts([query_text], settings)
    except Exception:
        logger.exception(
            "semantic query embedding failed person_id=%s cv_id=%s", person_id, cv_id
        )
        return []
    if not embedded:
        logger.warning(
            "semantic query embedding empty person_id=%s cv_id=%s",
            person_id,
            cv_id,
        )
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
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning(
            "pinecone query failed person_id=%s cv_id=%s error=%s",
            person_id,
            cv_id,
            exc,
        )
        return []
    except Exception:
        logger.exception("pinecone query unexpected error person_id=%s cv_id=%s", person_id, cv_id)
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
