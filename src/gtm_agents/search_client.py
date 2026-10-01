"""Fetch search candidates through MCP without an LLM controlling retries."""

import asyncio
import json
import os
from concurrent.futures import ThreadPoolExecutor

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def _search(query):
    url = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")

    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "search_market", arguments={"query": query}
            )

            if result.isError:
                raise RuntimeError("MCP search tool reported an error.")

            # FastMCP may provide structured data or JSON text.
            structured = getattr(result, "structuredContent", None)
            if isinstance(structured, dict):
                candidates = structured.get("result")
                if isinstance(candidates, list):
                    return candidates

            for block in result.content:
                if getattr(block, "type", None) == "text":
                    try:
                        candidates = json.loads(block.text)
                    except (TypeError, ValueError):
                        continue
                    if isinstance(candidates, list):
                        return candidates

            raise ValueError("MCP returned an unexpected search format.")


def fetch_candidates(query):
    """Make one tool call; the MCP server owns bounded HTTP retries."""
    # Use a separate thread so this also works within an existing event loop.
    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(
            asyncio.run, asyncio.wait_for(_search(query), timeout=60)
        ).result()