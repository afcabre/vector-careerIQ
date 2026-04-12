from hashlib import sha1
import logging
import json
import re
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
CHUNKING_VERSION = "v1"
CHUNKING_STRATEGY_TOKEN_WINDOW = "token_window"
CHUNKING_STRATEGY_SEMANTIC_SECTIONS = "semantic_sections"
CHUNKING_STRATEGIES = {
    CHUNKING_STRATEGY_TOKEN_WINDOW,
    CHUNKING_STRATEGY_SEMANTIC_SECTIONS,
}
DEFAULT_CHUNK_SECTION = "general"
SEMANTIC_MIN_SECTION_CHARS = 280


def normalize_chunking_strategy(value: str | None) -> str:
    candidate = str(value or "").strip().lower()
    if candidate in CHUNKING_STRATEGIES:
        return candidate
    return CHUNKING_STRATEGY_TOKEN_WINDOW


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


def _chunk_text_fallback(raw_text: str, section: str = DEFAULT_CHUNK_SECTION) -> list[dict[str, str]]:
    text = raw_text.strip()
    if not text:
        return []
    chunks: list[dict[str, str]] = []
    start = 0
    step = max(1, CHUNK_TARGET_CHARS - CHUNK_OVERLAP_CHARS)
    while start < len(text) and len(chunks) < MAX_CHUNKS:
        chunk = text[start : start + CHUNK_TARGET_CHARS].strip()
        if chunk:
            chunks.append({"text": chunk, "section": section})
        start += step
    return chunks


def _chunk_text_token_window(
    raw_text: str,
    settings: Settings,
    section: str = DEFAULT_CHUNK_SECTION,
) -> list[dict[str, str]]:
    text = raw_text.strip()
    if not text:
        return []

    encoder = _token_encoder(settings)
    if encoder is None:
        return _chunk_text_fallback(text, section=section)

    token_ids = encoder.encode(text)
    if not token_ids:
        return []

    chunks: list[dict[str, str]] = []
    start = 0
    step = max(1, CHUNK_STEP_TOKENS)
    while start < len(token_ids) and len(chunks) < MAX_CHUNKS:
        chunk_ids = token_ids[start : start + CHUNK_TARGET_TOKENS]
        if not chunk_ids:
            break
        chunk = encoder.decode(chunk_ids).strip()
        if chunk:
            chunks.append({"text": chunk, "section": section})
        start += step
    return chunks


def _split_markdown_sections(markdown_text: str) -> list[tuple[str, str]]:
    text = markdown_text.strip()
    if not text:
        return []
    sections: list[tuple[str, str]] = []
    current_title = DEFAULT_CHUNK_SECTION
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        match = re.match(r"^\s{0,3}#{1,6}\s+(.+)$", line)
        if match:
            body = "\n".join(current_lines).strip()
            if body:
                sections.append((current_title, body))
            current_title = match.group(1).strip().lower() or DEFAULT_CHUNK_SECTION
            current_lines = []
            continue
        current_lines.append(line)

    body = "\n".join(current_lines).strip()
    if body:
        sections.append((current_title, body))
    return sections


def _chunk_text_semantic_sections(
    raw_text: str,
    markdown_text: str,
    settings: Settings,
) -> list[dict[str, str]]:
    sections = _split_markdown_sections(markdown_text)
    if not sections:
        return []

    chunks: list[dict[str, str]] = []
    pending_section = DEFAULT_CHUNK_SECTION
    pending_text = ""
    for section, body in sections:
        normalized_section = section.strip().lower() or DEFAULT_CHUNK_SECTION
        candidate = body.strip()
        if not candidate:
            continue

        if pending_text and len(pending_text) < SEMANTIC_MIN_SECTION_CHARS:
            pending_text = f"{pending_text}\n\n{candidate}".strip()
        else:
            if pending_text:
                chunks.extend(
                    _chunk_text_token_window(
                        pending_text,
                        settings,
                        section=pending_section,
                    )
                )
                if len(chunks) >= MAX_CHUNKS:
                    return chunks[:MAX_CHUNKS]
            pending_section = normalized_section
            pending_text = candidate

    if pending_text:
        chunks.extend(
            _chunk_text_token_window(
                pending_text,
                settings,
                section=pending_section,
            )
        )
    if not chunks and raw_text.strip():
        return _chunk_text_token_window(raw_text, settings, section=DEFAULT_CHUNK_SECTION)
    return chunks[:MAX_CHUNKS]


def _chunk_text(
    raw_text: str,
    markdown_text: str,
    settings: Settings,
    chunking_strategy: str,
) -> tuple[list[dict[str, str]], str]:
    normalized_strategy = normalize_chunking_strategy(chunking_strategy)
    if normalized_strategy == CHUNKING_STRATEGY_SEMANTIC_SECTIONS:
        semantic_chunks = _chunk_text_semantic_sections(raw_text, markdown_text, settings)
        if semantic_chunks:
            return semantic_chunks, CHUNKING_STRATEGY_SEMANTIC_SECTIONS
    return (
        _chunk_text_token_window(raw_text, settings, section=DEFAULT_CHUNK_SECTION),
        CHUNKING_STRATEGY_TOKEN_WINDOW,
    )


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
    chunking_strategy: str,
) -> tuple[str, int, str, str, str]:
    person_id = str(record.get("person_id", "")).strip()
    cv_id = str(record.get("cv_id", "")).strip()
    normalized_strategy = normalize_chunking_strategy(chunking_strategy)

    if not _is_ready(settings):
        logger.warning(
            "vector upsert skipped due to missing config person_id=%s cv_id=%s",
            person_id,
            cv_id,
        )
        return "skipped_missing_vector_config", 0, normalized_strategy, CHUNKING_VERSION, "plain_text"

    text = str(record.get("extracted_text", "")).strip()
    markdown_text = str(record.get("structured_markdown", "")).strip()
    chunks, applied_strategy = _chunk_text(
        text,
        markdown_text,
        settings,
        normalized_strategy,
    )
    vector_source_format = (
        "markdown_structured"
        if applied_strategy == CHUNKING_STRATEGY_SEMANTIC_SECTIONS and bool(markdown_text)
        else "plain_text"
    )
    if not chunks:
        logger.warning(
            "vector upsert skipped due to empty text person_id=%s cv_id=%s",
            person_id,
            cv_id,
        )
        return "skipped_empty_cv_text", 0, applied_strategy, CHUNKING_VERSION, vector_source_format

    try:
        embeddings = _embed_texts([item["text"] for item in chunks], settings)
    except Exception:
        logger.exception(
            "embedding generation failed person_id=%s cv_id=%s", person_id, cv_id
        )
        return "failed_embedding", 0, applied_strategy, CHUNKING_VERSION, vector_source_format
    if not embeddings or len(embeddings) != len(chunks):
        logger.warning(
            "embedding shape mismatch person_id=%s cv_id=%s chunks=%s vectors=%s",
            person_id,
            cv_id,
            len(chunks),
            len(embeddings),
        )
        return "failed_embedding_shape", 0, applied_strategy, CHUNKING_VERSION, vector_source_format

    vectors: list[dict[str, Any]] = []
    for index, (chunk, values) in enumerate(zip(chunks, embeddings, strict=False)):
        digest = sha1(f"{cv_id}:{index}".encode("utf-8")).hexdigest()[:12]
        vector_id = f"cv-{cv_id}-{digest}"
        vectors.append(
            {
                "id": vector_id,
                "values": values,
                "metadata": {
                    "person_id": person_id,
                    "cv_id": cv_id,
                    "chunk_id": vector_id,
                    "chunk_index": index,
                    "section": str(chunk.get("section", DEFAULT_CHUNK_SECTION)).strip().lower()
                    or DEFAULT_CHUNK_SECTION,
                    "chunking_strategy": applied_strategy,
                    "chunking_version": CHUNKING_VERSION,
                    "source_format": vector_source_format,
                    "text": str(chunk.get("text", "")).strip(),
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
        return "failed_pinecone_upsert", 0, applied_strategy, CHUNKING_VERSION, vector_source_format
    except Exception:
        logger.exception("pinecone upsert unexpected error person_id=%s cv_id=%s", person_id, cv_id)
        return "failed_pinecone_upsert", 0, applied_strategy, CHUNKING_VERSION, vector_source_format

    return "indexed", len(vectors), applied_strategy, CHUNKING_VERSION, vector_source_format


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
