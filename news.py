from html import unescape
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

import requests
from requests.exceptions import SSLError
from urllib3.exceptions import InsecureRequestWarning
import urllib3


FEED_URL = "https://techcrunch.com/feed/"
HEADERS = {"User-Agent": "NewsApp/1.0 (+https://localhost)"}


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self):
        return " ".join(self.parts)


def clean_html(value):
    parser = _TextExtractor()
    parser.feed(unescape(value or ""))
    return parser.text()


def _find_text(item, tag_name):
    tag = item.find(tag_name)
    return tag.text.strip() if tag is not None and tag.text else ""


def fetch_news(limit=20):
    session = requests.Session()
    session.trust_env = False

    try:
        response = session.get(FEED_URL, headers=HEADERS, timeout=10)
    except SSLError:
        urllib3.disable_warnings(InsecureRequestWarning)
        response = session.get(FEED_URL, headers=HEADERS, timeout=10, verify=False)

    response.raise_for_status()

    root = ET.fromstring(response.content)
    items = root.findall(".//item")

    articles = []
    for item in items[:limit]:
        articles.append(
            {
                "title": _find_text(item, "title"),
                "link": _find_text(item, "link"),
                "description": clean_html(_find_text(item, "description")),
                "published_at": _find_text(item, "pubDate"),
            }
        )

    return articles


if __name__ == "__main__":
    for article in fetch_news():
        print(article)
        print()
