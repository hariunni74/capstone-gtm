import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


async def main():
    async with streamable_http_client(
        "http://localhost:8000/mcp"
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools:", [tool.name for tool in tools.tools])

            result = await session.call_tool(
                "search_market",
                arguments={"query": "Key features of product discovery competitors"},
            )
            print("Tool error:", result.isError)
            print("First content:", result.content[0].text[:500])


if __name__ == "__main__":
    asyncio.run(main())