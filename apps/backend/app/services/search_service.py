from datetime import UTC, datetime
from hashlib import sha1
import logging
import json
from typing import Any, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from app.core.settings import Settings
from app.services.person_store import PersonRecord
from app.services.prompt_config_store import FLOW_SEARCH_JOBS_TAVILY, build_prompt_query
from app.services.request_trace_store import add_request_trace
from app.services.search_provider_store import (
    PROVIDER_ADZUNA,
    PROVIDER_REMOTIVE,
    PROVIDER_TAVILY,
    is_search_provider_enabled,
)

logger = logging.getLogger(__name__)
TAVILY_MAX_QUERY_CHARS = 400


class SearchResult(TypedDict):
    search_result_id: str
    source_provider: str
    source_url: str
    title: str
    company: str
    location: str
    snippet: str
    captured_at: str
    normalized_payload: dict[str, Any]


class SearchResponse(TypedDict):
    items: list[SearchResult]
    warnings: list[str]


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat()


def _result_id(source_url: str, title: str, company: str) -> str:
    seed = f"{source_url}|{title}|{company}".encode("utf-8")
    return f"sr-{sha1(seed).hexdigest()[:12]}"


def _company_from_url(source_url: str) -> str:
    host = urlparse(source_url).netloc.replace("www.", "")
    if not host:
        return ""
    return host.split(".")[0].replace("-", " ").title()


def _short_text(raw: str, max_chars: int = 360) -> str:
    text = (raw or "").strip()
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."


def _normalize_url(source_url: str) -> str:
    cleaned = source_url.strip()
    if cleaned.endswith("/"):
        cleaned = cleaned[:-1]
    return cleaned


def _fallback_results(person: PersonRecord, query: str) -> list[SearchResult]:
    role = person["target_roles"][0] if person["target_roles"] else "Role"
    title = f"Resultado local para {role}"
    snippet = (
        f"No hubo resultados en proveedor externo para '{query}'. "
        "Revisa configuracion/habilitacion de proveedores o conectividad."
    )
    url = ""
    return [
        {
            "search_result_id": _result_id(url, title, person["full_name"]),
            "source_provider": "fallback",
            "source_url": url,
            "title": title,
            "company": "",
            "location": person["location"],
            "snippet": snippet,
            "captured_at": _now_iso(),
            "normalized_payload": {"query": query, "fallback": True},
        }
    ]


def _cap_tavily_query(query: str) -> tuple[str, bool]:
    cleaned = query.strip()
    if len(cleaned) <= TAVILY_MAX_QUERY_CHARS:
        return cleaned, False
    truncated = cleaned[:TAVILY_MAX_QUERY_CHARS].rstrip()
    return truncated, True


def _request_json(request: Request, timeout: int = 20) -> dict[str, Any]:
    with urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    payload = json.loads(raw)
    if isinstance(payload, dict):
        return payload
    return {}


def _tavily_search(query: str, max_results: int, settings: Settings) -> list[SearchResult]:
    payload = json.dumps(
        {
            "api_key": settings.tavily_api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
            "include_answer": False,
        }
    ).encode("utf-8")
    request = Request(
        url="https://api.tavily.com/search",
        method="POST",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    body = _request_json(request)

    items: list[SearchResult] = []
    for result in body.get("results", []):
        source_url = _normalize_url(str(result.get("url", "")))
        title = str(result.get("title", "")).strip() or "Untitled opportunity"
        snippet = _short_text(str(result.get("content", "")))
        company = _company_from_url(source_url)
        items.append(
            {
                "search_result_id": _result_id(source_url, title, company),
                "source_provider": "tavily",
                "source_url": source_url,
                "title": title,
                "company": company,
                "location": "",
                "snippet": snippet,
                "captured_at": _now_iso(),
                "normalized_payload": {
                    "score": result.get("score"),
                    "provider": "tavily",
                },
            }
        )
    return items


def _adzuna_search_via_rapidapi(
    query: str,
    max_results: int,
    settings: Settings,
) -> list[SearchResult]:
    if not settings.rapidapi_key or not settings.rapidapi_adzuna_host:
        return []

    encoded_query = quote_plus(query)
    url = (
        f"https://{settings.rapidapi_adzuna_host}/v1/api/jobs/us/search/1"
        f"?what={encoded_query}&results_per_page={max_results}&content-type=application/json"
    )
    request = Request(
        url=url,
        method="GET",
        headers={
            "X-RapidAPI-Key": settings.rapidapi_key,
            "X-RapidAPI-Host": settings.rapidapi_adzuna_host,
        },
    )
    body = _request_json(request)

    items: list[SearchResult] = []
    for result in body.get("results", []):
        title = str(result.get("title", "")).strip() or "Untitled opportunity"
        company_data = result.get("company", {})
        if isinstance(company_data, dict):
            company = str(company_data.get("display_name", "")).strip()
        else:
            company = str(company_data or "").strip()

        location_data = result.get("location", {})
        if isinstance(location_data, dict):
            location = str(location_data.get("display_name", "")).strip()
        else:
            location = str(location_data or "").strip()

        source_url = _normalize_url(
            str(
                result.get("redirect_url")
                or result.get("url")
                or result.get("adref")
                or ""
            )
        )
        snippet = _short_text(str(result.get("description", "")))
        items.append(
            {
                "search_result_id": _result_id(source_url, title, company),
                "source_provider": "adzuna",
                "source_url": source_url,
                "title": title,
                "company": company,
                "location": location,
                "snippet": snippet,
                "captured_at": _now_iso(),
                "normalized_payload": {
                    "provider": "adzuna_rapidapi",
                    "id": result.get("id"),
                    "salary_min": result.get("salary_min"),
                    "salary_max": result.get("salary_max"),
                },
            }
        )
    return items


def _remotive_search(
    query: str,
    max_results: int,
    settings: Settings,
) -> list[SearchResult]:
    encoded_query = quote_plus(query)
    url = f"https://remotive.com/api/remote-jobs?search={encoded_query}"
    headers: dict[str, str] = {}
    if settings.remotive_api_key:
        headers["Authorization"] = f"Bearer {settings.remotive_api_key}"

    request = Request(url=url, method="GET", headers=headers)
    body = _request_json(request)

    items: list[SearchResult] = []
    for result in body.get("jobs", [])[:max_results]:
        title = str(result.get("title", "")).strip() or "Untitled opportunity"
        company = str(result.get("company_name", "")).strip()
        location = str(result.get("candidate_required_location", "")).strip()
        source_url = _normalize_url(str(result.get("url", "")))
        snippet = _short_text(str(result.get("description", "")))
        items.append(
            {
                "search_result_id": _result_id(source_url, title, company),
                "source_provider": "remotive",
                "source_url": source_url,
                "title": title,
                "company": company,
                "location": location,
                "snippet": snippet,
                "captured_at": _now_iso(),
                "normalized_payload": {
                    "provider": "remotive",
                    "id": result.get("id"),
                    "job_type": result.get("job_type"),
                    "publication_date": result.get("publication_date"),
                },
            }
        )
    return items


def _dedupe(items: list[SearchResult]) -> list[SearchResult]:
    deduped: list[SearchResult] = []
    seen: set[str] = set()
    for item in items:
        source_url = _normalize_url(item["source_url"]).lower()
        if source_url:
            key = f"url:{source_url}"
        else:
            key = (
                f"fallback:{item['source_provider'].lower()}|"
                f"{item['title'].lower()}|{item['company'].lower()}"
            )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def search_opportunities(
    person: PersonRecord,
    query: str,
    max_results: int,
    settings: Settings,
) -> SearchResponse:
    warnings: list[str] = []
    query = query.strip()
    if not query:
        logger.warning("search skipped due to empty query")
        return {"items": [], "warnings": ["Empty query"]}

    items: list[SearchResult] = []
    provider_max_results = max(3, max_results)

    if not is_search_provider_enabled(PROVIDER_ADZUNA):
        warnings.append("Adzuna provider disabled from admin config")
        logger.warning("adzuna provider disabled from admin config")
    elif not settings.rapidapi_key or not settings.rapidapi_adzuna_host:
        warnings.append("Adzuna via RapidAPI is not configured")
        logger.warning("adzuna provider disabled due to missing RapidAPI config")
    else:
        try:
            add_request_trace(
                person_id=person["person_id"],
                destination="adzuna",
                flow_key="search_jobs_adzuna",
                request_payload={
                    "method": "GET",
                    "url": (
                        f"https://{settings.rapidapi_adzuna_host}/v1/api/jobs/us/search/1"
                        f"?what={quote_plus(query)}&results_per_page={provider_max_results}&content-type=application/json"
                    ),
                    "query": query,
                    "max_results": provider_max_results,
                },
            )
            items.extend(_adzuna_search_via_rapidapi(query, provider_max_results, settings))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            warnings.append("Adzuna provider failed, continuing with partial results")
            logger.warning("adzuna provider failed: %s", exc)
        except Exception:
            warnings.append("Adzuna provider unexpected error, continuing")
            logger.exception("adzuna provider unexpected error")

    if not is_search_provider_enabled(PROVIDER_REMOTIVE):
        warnings.append("Remotive provider disabled from admin config")
        logger.warning("remotive provider disabled from admin config")
    else:
        try:
            add_request_trace(
                person_id=person["person_id"],
                destination="remotive",
                flow_key="search_jobs_remotive",
                request_payload={
                    "method": "GET",
                    "url": f"https://remotive.com/api/remote-jobs?search={quote_plus(query)}",
                    "query": query,
                    "max_results": provider_max_results,
                },
            )
            items.extend(_remotive_search(query, provider_max_results, settings))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            warnings.append("Remotive provider failed, continuing with partial results")
            logger.warning("remotive provider failed: %s", exc)
        except Exception:
            warnings.append("Remotive provider unexpected error, continuing")
            logger.exception("remotive provider unexpected error")

    if not is_search_provider_enabled(PROVIDER_TAVILY):
        warnings.append("Tavily provider disabled from admin config")
        logger.warning("tavily provider disabled from admin config")
    elif settings.tavily_api_key:
        try:
            tavily_query = build_prompt_query(
                flow_key=FLOW_SEARCH_JOBS_TAVILY,
                context={
                    "query": query,
                    "person_full_name": person["full_name"],
                    "target_roles": ", ".join(person["target_roles"][:3]),
                    "skills": ", ".join(person["skills"][:10]),
                    "person_location": person["location"],
                },
                fallback=query,
            )
            tavily_query, was_truncated = _cap_tavily_query(tavily_query)
            if was_truncated:
                warnings.append("Tavily query exceeded 400 chars and was truncated")
                logger.warning(
                    "tavily query truncated to max chars person_id=%s",
                    person["person_id"],
                )
            add_request_trace(
                person_id=person["person_id"],
                destination="tavily",
                flow_key="search_jobs_tavily",
                request_payload={
                    "method": "POST",
                    "url": "https://api.tavily.com/search",
                    "body": {
                        "query": tavily_query,
                        "max_results": provider_max_results,
                        "search_depth": "basic",
                        "include_answer": False,
                    },
                },
            )
            tavily_items = _tavily_search(tavily_query, provider_max_results, settings)
            for item in tavily_items:
                item["location"] = item["location"] or person["location"]
                item["normalized_payload"]["query_used"] = tavily_query
            items.extend(tavily_items)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            warnings.append("Tavily provider failed, continuing with partial results")
            logger.warning("tavily provider failed: %s", exc)
        except Exception:
            warnings.append("Tavily provider unexpected error, continuing")
            logger.exception("tavily provider unexpected error")
    else:
        warnings.append("Tavily API key is missing")
        logger.warning("tavily provider disabled due to missing API key")

    deduped = _dedupe(items)
    if not deduped:
        warnings.append("All providers returned empty or failed, using fallback result")
        logger.warning(
            "search fallback activated for person_id=%s query=%s",
            person["person_id"],
            query,
        )
        items = _fallback_results(person, query)
    else:
        items = deduped[:max_results]

    return {"items": items, "warnings": warnings}
