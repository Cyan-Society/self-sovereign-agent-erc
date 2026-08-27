#!/usr/bin/env python3
"""
Test client for the Lit PKP Signer MCP Server.

Tests the basic functionality without actually signing transactions.
"""

import asyncio
import os
from fastmcp import Client
from fastmcp.client.auth import BearerAuth

async def test_server():
    """Test the MCP server tools."""
    
    api_key = os.environ.get("MCP_API_KEY")
    if not api_key:
        raise RuntimeError("MCP_API_KEY must be set for the integration test")

    print("Connecting to Lit PKP Signer MCP Server...")

    async with Client(
        "http://localhost:8001/mcp",
        auth=BearerAuth(api_key),
    ) as client:
        # List available tools
        print("\n📋 Available tools:")
        tools = await client.list_tools()
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:60]}...")
        
        # Test get_pkp_balance
        print("\n💰 Testing get_pkp_balance...")
        result = await client.call_tool("get_pkp_balance", {})
        print(f"  Result: {result}")
        
        # Test verify_state_anchor for token 1 (Kieran's token)
        print("\n🔍 Testing verify_state_anchor for token 1...")
        result = await client.call_tool("verify_state_anchor", {"token_id": 1})
        print(f"  Result: {result}")
        
        # Test verify_state_anchor for token 2 (PKP's token)
        print("\n🔍 Testing verify_state_anchor for token 2...")
        result = await client.call_tool("verify_state_anchor", {"token_id": 2})
        print(f"  Result: {result}")
        
        print("\n✅ Basic tests passed!")
        print("\nNote: anchor_state_via_pkp not tested (would cost gas)")


if __name__ == "__main__":
    asyncio.run(test_server())
