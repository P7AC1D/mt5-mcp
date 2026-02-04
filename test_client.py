"""Test script for MCP MT5 server."""
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


async def test():
    print("Connecting to MCP server...")
    async with sse_client("http://127.0.0.1:8000/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected!\n")

            # List tools
            tools = await session.list_tools()
            print(f"Available tools ({len(tools.tools)}):")
            for t in tools.tools[:5]:
                print(f"  - {t.name}")
            print("  ...")

            # List resources
            resources = await session.list_resources()
            print(f"\nAvailable resources ({len(resources.resources)}):")
            for r in resources.resources:
                print(f"  - {r.uri}")

            # Call get_account_info tool
            print("\n--- Calling get_account_info ---")
            result = await session.call_tool("get_account_info", {})
            print(result.content[0].text)

            # Get available symbols first
            print("\n--- Getting available symbols (first 10) ---")
            result = await session.call_tool("get_symbols", {"visible_only": True})
            symbols_data = json.loads(result.content[0].text)
            if isinstance(symbols_data, list) and len(symbols_data) > 0:
                for s in symbols_data[:10]:
                    name = s.get("name", s) if isinstance(s, dict) else s
                    print(f"  - {name}")
                
                # Try the first symbol
                first_symbol = symbols_data[0].get("name", symbols_data[0]) if isinstance(symbols_data[0], dict) else symbols_data[0]
                print(f"\n--- Calling get_symbol_tick for {first_symbol} ---")
                result = await session.call_tool("get_symbol_tick", {"symbol": first_symbol})
                print(result.content[0].text)
            else:
                print("No visible symbols found")

            # Read positions resource
            print("\n--- Reading mt5://positions resource ---")
            result = await session.read_resource("mt5://positions")
            print(result.contents[0].text)


if __name__ == "__main__":
    asyncio.run(test())
