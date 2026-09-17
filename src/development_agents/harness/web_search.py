"""
Tavily web search — raw HTTP, no SDK, matching llm_client.py's approach.
"""

import json
import urllib.error
import urllib.request


class SearchError(RuntimeError):
    pass


def search(api_key: str, query: str, max_results: int = 5) -> list[dict]:
    """
    Returns up to max_results results as [{"title": ..., "url": ..., "content": ...}].
    Trimmed to just these three fields — Tavily's raw response includes extra
    fields (relevance score, raw_content, etc.) not needed here.
    """
    body = {"api_key": api_key, "query": query, "max_results": max_results}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        "https://api.tavily.com/search",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SearchError(f"Tavily returned HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise SearchError(f"Could not reach Tavily: {e.reason}") from e

    results = payload.get("results", [])
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
        }
        for r in results
    ]
