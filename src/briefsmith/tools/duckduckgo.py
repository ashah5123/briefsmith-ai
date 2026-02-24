"""DuckDuckGo HTML search client with optional caching."""

from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from briefsmith.schemas import SourceItem
from briefsmith.tools.cache import SearchCache
from briefsmith.tools.utils import deduplicate_sources, normalize_url

DDG_HTML_URL = "https://html.duckduckgo.com/html/"
USER_AGENT = "Mozilla/5.0 (compatible; Briefsmith/1.0; +https://github.com/briefsmith)"


class DuckDuckGoSearchClient:
    """WebSearchClient implementation using DuckDuckGo HTML (no API key)."""

    def __init__(
        self,
        cache: SearchCache | None = None,
        base_url: str = DDG_HTML_URL,
        timeout: int = 15,
    ) -> None:
        self._cache = cache
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def search(self, query: str, max_results: int = 5) -> list[SourceItem]:
        """Search DuckDuckGo HTML; return normalized, deduplicated SourceItems."""
        q = query.strip()
        if not q:
            return []

        if self._cache is not None:
            cached = self._cache.get(q)
            if cached is not None:
                return cached[:max_results]

        raw = self._fetch(q)
        items = self._parse(raw, q)
        items = deduplicate_sources(items)
        items = items[:max_results]

        if self._cache is not None:
            self._cache.set(q, items)

        return items

    def _fetch(self, query: str) -> str:
        """POST to DuckDuckGo HTML; return response text."""
        headers = {"User-Agent": USER_AGENT}
        data = {"q": query}
        try:
            resp = requests.post(
                self._base_url,
                data=data,
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as e:
            raise RuntimeError(
                f"DuckDuckGo request failed: {e}. Check network and URL."
            ) from e

    def _parse(self, html: str, base_query: str) -> list[SourceItem]:
        """Parse HTML into SourceItems; resolve relative URLs; normalize."""
        soup = BeautifulSoup(html, "html.parser")
        results = soup.select("div.result")
        if not results:
            results = soup.select("div.web-result")
        items: list[SourceItem] = []
        base = self._base_url.rstrip("/") + "/"
        for node in results:
            link_el = (
                node.select_one("a.result__a")
                or node.select_one("a.result__url")
                or node.select_one("a[href]")
            )
            if not link_el or not link_el.get("href"):
                continue
            href = link_el.get("href", "").strip()
            if not href or href.startswith("#"):
                continue
            if href.startswith("/"):
                href = urljoin(base, href)
            if "duckduckgo.com" in urlparse(href).netloc:
                continue
            url = normalize_url(href)
            title = (link_el.get_text() or "").strip() or None
            snippet_el = (
                node.select_one("a.result__snippet")
                or node.select_one("div.result__snippet")
                or node.select_one(".snippet")
            )
            snippet = (snippet_el.get_text() if snippet_el else "").strip() or ""
            items.append(
                SourceItem(
                    url=url,
                    title=title,
                    snippet=snippet,
                    accessed_at=datetime.now(UTC),
                )
            )
        return items
