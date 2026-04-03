from datetime import UTC, datetime
from hashlib import sha1
import json
from typing import Any, TypedDict
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from app.core.settings import Settings
from app.services.person_store import PersonRecord


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


def _fallback_results(person: PersonRecord, query: str) -> list[SearchResult]:
    role = person["target_roles"][0] if person["target_roles"] else "Role"
    title = f"Resultado local para {role}"
    snippet = (
        f"No hubo resultados en proveedor externo para '{query}'. "
        "Verifica API key de Tavily o conectividad de red."
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


def _tavily_search(query: str, max_results: int, settings: Settings) -> list[dict[str, Any]]:
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
    with urlopen(request, timeout=20) as response:
        raw = response.read().decode("utf-8")
    body = json.loads(raw)
    return body.get("results", [])


def search_opportunities(
    person: PersonRecord,
    query: str,
    max_results: int,
    settings: Settings,
) -> SearchResponse:
    warnings: list[str] = []
    query = query.strip()
    if not query:
        return {"items": [], "warnings": ["Empty query"]}

    if not settings.tavily_api_key:
        warnings.append("Missing Tavily API key, using fallback results")
        return {"items": _fallback_results(person, query), "warnings": warnings}

    try:
        raw_results = _tavily_search(query, max_results, settings)
    except (URLError, TimeoutError, json.JSONDecodeError):
        warnings.append("Tavily search failed, using fallback results")
        return {"items": _fallback_results(person, query), "warnings": warnings}
    except Exception:
        warnings.append("Unexpected search provider error, using fallback results")
        return {"items": _fallback_results(person, query), "warnings": warnings}

    items: list[SearchResult] = []
    for result in raw_results:
        source_url = str(result.get("url", "")).strip()
        title = str(result.get("title", "")).strip() or "Untitled opportunity"
        snippet = str(result.get("content", "")).strip()
        company = _company_from_url(source_url)
        normalized_payload = {
            "score": result.get("score"),
            "query": query,
            "provider": "tavily",
        }
        items.append(
            {
                "search_result_id": _result_id(source_url, title, company),
                "source_provider": "tavily",
                "source_url": source_url,
                "title": title,
                "company": company,
                "location": person["location"],
                "snippet": snippet,
                "captured_at": _now_iso(),
                "normalized_payload": normalized_payload,
            }
        )

    if not items:
        warnings.append("Provider returned no results, using fallback result")
        items = _fallback_results(person, query)

    return {"items": items, "warnings": warnings}
