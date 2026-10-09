"""Read-only SDK v2 smoke client. Never submits trades or changes accounts."""

import argparse
import asyncio
import json
import os

import httpx2
from mcp.client import Client
from mcp.client.streamable_http import streamable_http_client


async def smoke(url: str) -> None:
    token = os.environ.get("MT5_HTTP_TOKEN")
    headers = {"Authorization": "Bearer " + token} if token else {}
    async with httpx2.AsyncClient(headers=headers) as http:
        async with Client(streamable_http_client(url, http_client=http)) as client:
            print(f"Tools: {len((await client.list_tools()).tools)}")
            result = await client.call_tool("get_positions_count", {})
            if result.is_error:
                raise RuntimeError(result.structured_content)
            print(json.dumps(result.structured_content))
            print(f"Resources: {len((await client.list_resources()).resources)}")
            print(f"Templates: {len((await client.list_resource_templates()).resource_templates)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000/mcp")
    asyncio.run(smoke(parser.parse_args().url))
