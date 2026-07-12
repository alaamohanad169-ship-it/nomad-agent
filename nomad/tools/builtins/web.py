"""Web tools — search and extract."""
import json
import re
from urllib.parse import quote_plus

import httpx

from nomad.tools.registry import registry, ToolSchema, ToolRisk


async def web_search(query: str, limit: int = 5) -> str:
    """Search the web using DuckDuckGo."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Android; Mobile) Nomad/0.1",
        }
        
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            resp.raise_for_status()
        
        # Parse results from HTML
        results = []
        # DuckDuckGo HTML result blocks
        blocks = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            resp.text, re.DOTALL
        )
        
        for href, title, snippet in blocks[:limit]:
            # Clean HTML tags
            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            # Decode URL
            if "uddg=" in href:
                href = re.search(r'uddg=([^&]+)', href)
                if href:
                    from urllib.parse import unquote
                    href = unquote(href.group(1))
            
            results.append({
                "title": title,
                "url": href,
                "snippet": snippet[:300],
            })
        
        return json.dumps({"results": results, "query": query})
    
    except Exception as e:
        return json.dumps({"error": str(e), "query": query})


async def web_extract(urls: list[str], char_limit: int = 5000) -> str:
    """Extract text content from web pages."""
    results = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Android; Mobile) Nomad/0.1",
    }
    
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url in urls[:3]:  # Max 3 URLs
            try:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                
                # Basic HTML to text
                text = resp.text
                # Remove scripts and styles
                text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                # Remove HTML tags
                text = re.sub(r'<[^>]+>', ' ', text)
                # Collapse whitespace
                text = re.sub(r'\s+', ' ', text).strip()
                # Truncate
                text = text[:char_limit]
                
                results.append({
                    "url": url,
                    "title": re.search(r'<title>(.*?)</title>', resp.text, re.DOTALL),
                    "content": text,
                    "chars": len(text),
                })
                # Extract title properly
                title_match = re.search(r'<title>(.*?)</title>', resp.text, re.DOTALL)
                if title_match and results:
                    results[-1]["title"] = title_match.group(1).strip()
                    
            except Exception as e:
                results.append({"url": url, "error": str(e)})
    
    return json.dumps({"results": results})


# Register tools
registry.register(ToolSchema(
    name="web_search",
    description="Search the web using DuckDuckGo. Returns titles, URLs, and snippets.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results (default 5)"},
        },
        "required": ["query"],
    },
    risk=ToolRisk.SAFE,
    handler=web_search,
))

registry.register(ToolSchema(
    name="web_extract",
    description="Extract text content from web page URLs. Returns cleaned text content.",
    parameters={
        "type": "object",
        "properties": {
            "urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "URLs to extract (max 3)",
            },
            "char_limit": {
                "type": "integer",
                "description": "Max chars per page (default 5000)",
            },
        },
        "required": ["urls"],
    },
    risk=ToolRisk.SAFE,
    handler=web_extract,
))
