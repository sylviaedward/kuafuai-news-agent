from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

FEEDS = {
    "Google AI Blog": "https://blog.google/innovation-and-ai/technology/ai/rss/",
    "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
    "arXiv cs.LG": "https://rss.arxiv.org/rss/cs.LG",
    "MarkTechPost": "https://www.marktechpost.com/feed/",
}
MAX_FEED_BYTES = 2_000_000
ATOM = "{http://www.w3.org/2005/Atom}"


def clean_text(value: str | None, limit: int = 500) -> str:
    value = html.unescape(re.sub(r"<[^>]*>", " ", value or ""))
    return re.sub(r"\s+", " ", value).strip()[:limit]


def parse_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        except ValueError:
            return None


def parse_feed(xml_bytes: bytes, source: str) -> list[dict]:
    root = ElementTree.fromstring(xml_bytes)
    result = []
    entries = root.findall("./channel/item") or root.findall(f"./{ATOM}entry")
    for entry in entries:
        title = clean_text(entry.findtext("title") or entry.findtext(f"{ATOM}title"), 200)
        link = entry.findtext("link")
        if link is None:
            link_node = entry.find(f"{ATOM}link")
            link = link_node.attrib.get("href") if link_node is not None else None
        summary = clean_text(entry.findtext("description") or entry.findtext(f"{ATOM}summary"), 450)
        published = parse_date(entry.findtext("pubDate") or entry.findtext(f"{ATOM}published")
                               or entry.findtext(f"{ATOM}updated"))
        if title and link and link.startswith(("https://", "http://")):
            result.append({"id": hashlib.sha256(link.encode()).hexdigest()[:16],
                           "title": title, "url": link, "source": source,
                           "published_at": published, "excerpt": summary})
    return result


def retrieve_all_news() -> tuple[list[dict], list[str]]:
    articles: dict[str, dict] = {}
    errors = []
    with httpx.Client(timeout=10, follow_redirects=True,
                      headers={"User-Agent": "KUAFUAI-News-Agent/1.0 (RSS reader)"}) as client:
        for source, url in FEEDS.items():
            try:
                response = client.get(url)
                response.raise_for_status()
                if len(response.content) > MAX_FEED_BYTES:
                    raise ValueError("feed too large")
                for article in parse_feed(response.content, source):
                    articles[article["id"]] = article
            except (httpx.HTTPError, ValueError, ElementTree.ParseError) as exc:
                errors.append(f"{source}: {type(exc).__name__}")
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    recent = [a for a in articles.values() if a["published_at"] and
              datetime.fromisoformat(a["published_at"]) >= cutoff]
    recent.sort(key=lambda a: a["published_at"], reverse=True)
    return recent[:100], errors


def search_articles(articles: list[dict], query: str, limit: int = 12) -> dict:
    query = query.strip().lower()
    words = [w for w in re.split(r"[\s,，、]+", query) if w]
    if words:
        scored = []
        for article in articles:
            text = (article["title"] + " " + article["excerpt"]).lower()
            score = sum(3 if word in article["title"].lower() else 1
                        for word in words if word in text)
            if score:
                scored.append((score, article))
        scored.sort(key=lambda pair: (pair[0], pair[1]["published_at"]), reverse=True)
        result = [a for _, a in scored[:limit]]
    else:
        result = articles[:limit]
    return {"query": query, "match_count": len(result), "articles": result,
            "hint": "No lexical match. Try a broader or English query." if not result else ""}

