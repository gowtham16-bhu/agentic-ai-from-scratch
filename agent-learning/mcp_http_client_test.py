import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    # No subprocess spawn here -- we just point at an already-running server's URL.
    # This is the only real conceptual difference from the stdio client.
    async with sse_client("http://127.0.0.1:8765/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools:", [t.name for t in tools.tools])

            result = await session.call_tool("calculator", {"expression": "47 * 89"})
            print("calculator('47 * 89') ->", result.content[0].text)


            result = await session.call_tool("word_count",{ "text": "hello world foo"})
            print("word_count(...) ->", result.content[0].text)

asyncio.run(main())
