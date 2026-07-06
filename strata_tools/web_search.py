"""imprint/web_search.py — give the local assistant eyes on the web.

Ported from Sentinel Forge's proven implementation: DuckDuckGo's
lightweight HTML endpoint via standard-library urllib (no API key, no
account). BeautifulSoup improves parsing when present; a regex fallback
keeps it working without it. The model itself never touches the network —
the app searches and hands the model compact text results.
"""
from __future__ import annotations

import re

try:
    from bs4 import BeautifulSoup as _BS
except Exception:
    _BS = None


def web_search_context(query: str, limit: int = 5) -> str:
    """Compact 'Web search results for: …' context block, or an honest
    failure line. Never raises."""
    query = (query or "").strip()
    if not query:
        return ""
    try:
        import html as html_lib
        import urllib.parse
        import urllib.request

        url = ("https://lite.duckduckgo.com/lite/?"
               + urllib.parse.urlencode({"q": query}))
        req = urllib.request.Request(
            url,
            headers={"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; "
                                    "x64) Imprint/1.0")},
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read(300_000).decode("utf-8", errors="replace")

        results = []

        def _clean_href(href: str) -> str:
            href = html_lib.unescape(href or "").strip()
            if href.startswith("//"):
                href = "https:" + href
            parsed = urllib.parse.urlparse(href)
            if ("duckduckgo.com" in parsed.netloc
                    and parsed.path.startswith("/l/")):
                target = urllib.parse.parse_qs(
                    parsed.query).get("uddg", [""])[0]
                if target:
                    return target
            return href

        if _BS is not None:
            soup = _BS(raw, "html.parser")
            for link in soup.select("a.result-link"):
                title = link.get_text(" ", strip=True)
                href = _clean_href(link.get("href") or "")
                row = link.find_parent("tr")
                node = (row.find_next("td", class_="result-snippet")
                        if row else None)
                snippet = node.get_text(" ", strip=True) if node else ""
                if title:
                    results.append((title, href, snippet))
                if len(results) >= limit:
                    break
        else:
            pattern = re.compile(
                r'<a[^>]+href="([^"]+)"[^>]+class=[\'\"]result-link'
                r'[\'\"][^>]*>(.*?)</a>',
                re.IGNORECASE | re.DOTALL)
            for href, title_html in pattern.findall(raw):
                title = re.sub(r"<[^>]+>", " ", title_html)
                title = html_lib.unescape(re.sub(r"\s+", " ", title)).strip()
                if title:
                    results.append((title, _clean_href(href), ""))
                if len(results) >= limit:
                    break

        if not results:
            return "Web search returned no usable results."
        lines = [f"Web search results for: {query}"]
        for i, (title, href, snippet) in enumerate(results, start=1):
            lines.append(f"{i}. {title}")
            if snippet:
                lines.append(f"   Summary: {snippet}")
            if href:
                lines.append(f"   Source: {href}")
        return "\n".join(lines)
    except Exception as e:
        return f"Web search failed: {type(e).__name__}: {e}"
