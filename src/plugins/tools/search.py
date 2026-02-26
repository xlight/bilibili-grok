"""Web search tool for Bilibili Grok agent."""


from langchain_core.tools import BaseTool, tool


@tool
async def search_web(query: str) -> str:
    """Search the web for information.

    Args:
        query: The search query

    Returns:
        Search results as a formatted string
    """
    try:
        import httpx
    except ImportError:
        return "Error: httpx not installed"

    try:
        response = await httpx.AsyncClient().get(
            "https://duckduckgo.com/",
            params={
                "q": query,
                "format": "json",
            },
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; BilibiliGrok/0.1.0)",
            },
            timeout=10.0,
        )

        if response.status_code != 200:
            return f"Search failed with status {response.status_code}"

        data = response.json()
        results = data.get("Results", [])

        if not results:
            return f"No results found for: {query}"

        formatted = []
        for i, result in enumerate(results[:5], 1):
            title = result.get("Text", "")
            url = result.get("FirstURL", "")
            formatted.append(f"{i}. {title}\n   {url}")

        return "\n\n".join(formatted)

    except Exception as e:
        return f"Search error: {str(e)}"


def create_search_tool() -> BaseTool:
    """Create the search tool."""
    return search_web
