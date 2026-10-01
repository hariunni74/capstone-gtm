import json
import os
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from dotenv import load_dotenv

load_dotenv()

params = {
    "engine": "google_light",
    "q": "WHO digital health strategy",
    "num": 3,
    "api_key": os.environ["SERPAPI_API_KEY"],
}

start = time.monotonic()

try:
    url = "https://serpapi.com/search.json?" + urlencode(params)
    with urlopen(url, timeout=20) as response:
        data = json.load(response)

    print("Status:", data.get("search_metadata", {}).get("status"))
    print("Results:", len(data.get("organic_results", [])))
    print("API error:", data.get("error", "none"))
except Exception as exc:
    print("Request failed:", type(exc).__name__)
finally:
    print("Elapsed seconds:", round(time.monotonic() - start, 1))