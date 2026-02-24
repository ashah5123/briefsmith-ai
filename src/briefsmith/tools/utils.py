"""URL normalization and source deduplication."""

from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from briefsmith.schemas import SourceItem


def normalize_url(url: str) -> str:
    """Remove UTM/tracking params and trailing slash."""
    parsed = urlparse(url.strip())
    if not parsed.scheme and not parsed.netloc and parsed.path.startswith("/"):
        return url.strip().rstrip("/")
    query = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in query.items() if not k.lower().startswith("utm_")}
    new_query = urlencode(filtered, doseq=True)
    new_parts = (
        parsed.scheme,
        parsed.netloc,
        parsed.path.rstrip("/") or "/",
        parsed.params,
        new_query,
        parsed.fragment,
    )
    result = urlunparse(new_parts)
    return result.rstrip("/") if result != "///" else result


def deduplicate_sources(sources: list[SourceItem]) -> list[SourceItem]:
    """Return sources deduplicated by normalized URL, preserving order."""
    seen: set[str] = set()
    out: list[SourceItem] = []
    for s in sources:
        key = normalize_url(s.url)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out
