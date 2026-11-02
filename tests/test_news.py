from app.news import parse_feed, search_articles


def test_rss_parse_and_search():
    xml = b"""<rss><channel><item><title>Agent model released</title>
    <link>https://example.org/agent</link><description>Open &amp; useful</description>
    <pubDate>Mon, 02 Nov 2026 08:00:00 +0000</pubDate></item></channel></rss>"""
    articles = parse_feed(xml, "test")
    assert articles[0]["excerpt"] == "Open & useful"
    assert search_articles(articles, "agent")["articles"][0]["id"] == articles[0]["id"]
    assert search_articles(articles, "robotics")["articles"] == []
