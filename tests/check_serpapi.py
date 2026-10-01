import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import HTTPError

from dotenv import load_dotenv

load_dotenv()

params = {
    "engine": "google",
    "q": "consumer healthcare product discovery market United States",
    "api_key": os.environ["SERPAPI_API_KEY"],
    "num": 3,
}
url = "https://serpapi.com/search.json?" + urlencode(params)

try:
    with urlopen(url, timeout=30) as response:
        data = json.load(response)
except HTTPError as error:
    raise SystemExit(f"SerpAPI HTTP error: {error.code}") from None

if "error" in data:
    raise SystemExit(f"SerpAPI error: {data['error']}")

results = [
    {"title": item.get("title"), "url": item.get("link")}
    for item in data.get("organic_results", [])[:3]
]

Path("outputs").mkdir(exist_ok=True)
Path("outputs/serpapi_check.json").write_text(
    json.dumps(results, indent=2), encoding="utf-8"
)

print(f"Search status: {data.get('search_metadata', {}).get('status')}")
print(f"Organic results saved: {len(results)}")
print("File: outputs/serpapi_check.json")