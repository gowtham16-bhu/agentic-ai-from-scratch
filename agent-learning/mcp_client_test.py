import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # this launches mcp_calculator_server.py as a subprocess and talks to it
    # over stdin/stdout using the MCP protocol
    server_params = StdioServerParameters(command="./venv/bin/python3", args=["mcp_calculator_server.py"])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Tools this server exposes:")
            for tool in tools.tools:
                print(f"  - {tool.name}: {tool.description}")

            result = await session.call_tool("calculator", {"expression": "47 * 89"})
            print("\ncalculator('47 * 89') ->", result.content[0].text)

            result = await session.call_tool("word_count", {"text": "this is a test sentence"})
            print("word_count(...) ->", result.content[0].text)

asyncio.run(main())
