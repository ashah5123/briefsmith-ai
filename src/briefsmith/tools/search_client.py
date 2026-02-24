"""Protocol for web search clients."""

from typing import Protocol, runtime_checkable

from briefsmith.schemas import SourceItem


@runtime_checkable
class WebSearchClient(Protocol):
    """Protocol for web search implementations (e.g. DuckDuckGo)."""

    def search(self, query: str, max_results: int = 5) -> list[SourceItem]:
        """Run a search and return a list of source items."""
        ...
