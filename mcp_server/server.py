import os
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("Capstone Research Tools", host="0.0.0.0", port=8000)


@mcp.tool()
def search_market(query: str) -> list[dict]:
    """Search the web for market and competitor research. Return linked search leads."""
    params = {
        "engine": "google_light",
        "q": query,
        "num": 5,
        "api_key": os.environ["SERPAPI_API_KEY"],
    }
    url = "https://serpapi.com/search.json?" + urlencode(params)

    for attempt in range(2):
        try:
            with urlopen(url, timeout=8) as response:
                data = json.load(response)
            break
        except TimeoutError:
            if attempt == 0:
                continue
            return [{
                "status": "error",
                "error_code": "timeout",
                "error": "SerpAPI search timed out on both attempts.",
                "retryable": False,
            }]
        except HTTPError as error:
            return [{
                "status": "error",
                "error_code": f"http_{error.code}",
                "error": f"SerpAPI returned HTTP {error.code}.",
                "retryable": error.code == 429 or error.code >= 500,
            }]

    if data.get("error"):
        return [{
            "status": "error",
            "error_code": "serpapi_error",
            "error": str(data["error"]),
            "retryable": False,
        }]

    return [
        {
            "title": result.get("title", ""),
            "url": result.get("link", ""),
            "snippet": result.get("snippet", ""),
        }
        for result in data.get("organic_results", [])[:5]
    ]

if __name__ == "__main__":
    mcp.run(transport="streamable-http")