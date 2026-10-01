from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_title = False
        self.in_paragraph = False
        self.title = ""
        self.paragraph_parts = []
        self.paragraph_links = 0
        self.paragraphs = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True
        elif tag.lower() == "p":
            self.in_paragraph = True
            self.paragraph_parts = []
            self.paragraph_links = 0
        elif tag.lower() == "a" and self.in_paragraph:
            self.paragraph_links += 1

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False
        elif tag.lower() == "p" and self.in_paragraph:
            paragraph = " ".join(" ".join(self.paragraph_parts).split())
            if (
                len(paragraph) >= 80
                and self.paragraph_links <= 2
                and any(mark in paragraph for mark in (".", "?", "!"))
            ):
                self.paragraphs.append(paragraph)
            self.in_paragraph = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_paragraph:
            self.paragraph_parts.append(data)


def check_source(url: str) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return {"url": url, "accessible": False, "error": "Expected an HTTPS URL"}

    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read(200_000)
            status = response.status
            final_url = response.geturl()
            content_type = response.headers.get_content_type()
    except HTTPError as error:
        return {
            "url": url,
            "accessible": False,
            "http_status": error.code,
            "access_status": "blocked" if error.code in (401, 403) else "http_error",
            "error": str(error),
        }
    except (URLError, TimeoutError) as error:
        return {
            "url": url,
            "accessible": False,
            "access_status": "fetch_failed",
            "error": str(error),
        }

    parser = PageParser()
    if content_type == "text/html":
        parser.feed(body.decode("utf-8", errors="replace"))

    return {
        "url": url,
        "final_url": final_url,
        "accessible": status == 200,
        "http_status": status,
        "content_type": content_type,
        "page_title": parser.title.strip(),
        "text_excerpt": " ".join(parser.paragraphs[:8])[:2500],
    }