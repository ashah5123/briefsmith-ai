"""Web search tools: DuckDuckGo client, cache, and utilities."""

from briefsmith.tools.cache import SearchCache
from briefsmith.tools.duckduckgo import DuckDuckGoSearchClient
from briefsmith.tools.search_client import WebSearchClient
from briefsmith.tools.utils import deduplicate_sources, normalize_url

__all__ = [
    "DuckDuckGoSearchClient",
    "SearchCache",
    "WebSearchClient",
    "deduplicate_sources",
    "normalize_url",
]
