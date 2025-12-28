#!/usr/bin/env python3
"""
Test API key authentication on the MCP server.

This verifies that:
1. Requests without api_key are rejected
2. Requests with wrong api_key are rejected  
3. Requests with correct api_key succeed
"""

import asyncio
import os
from pathlib import Path
from fastmcp import Client
from dotenv import load_dotenv

# Load environment
ENV_PATH = Path(__file__).parent.parent / '.env'
load_dotenv(ENV_PATH)
MCP_API_KEY = os.getenv('MCP_API_KEY')


async def test_auth():
    """Test authentication scenarios."""
    print("=" * 60)
    print("MCP Server Authentication Tests")
    print("=" * 60)
    
    async with Client("http://localhost:8847/mcp") as client:
        print("\n✅ Connected to MCP server")
        
        # Test 1: Read-only tool (should work without auth)
        print("\n--- Test 1: Read-only tool (no auth required) ---")
        result = await client.call_tool("get_pkp_balance", {})
        if result.is_error:
            print(f"   ❌ Unexpected error: {result.content}")
        else:
            data = result.data
            if "error" in data:
                print(f"   ❌ Error: {data['error']}")
            else:
                print(f"   ✅ Success! PKP balance: {data['balance_eth']} ETH")
        
        # Test 2: Signing tool WITHOUT api_key (should fail)
        print("\n--- Test 2: Signing tool WITHOUT api_key (should fail) ---")
        try:
            result = await client.call_tool("anchor_state_via_pkp", {
                "token_id": 2,
                "state_hash": "0x" + "ab" * 32,
                "state_uri": "test://auth-test"
                # NO api_key!
            })
            if result.is_error:
                print(f"   ✅ Correctly rejected (error in response): {result.content}")
            else:
                data = result.data
                if "error" in data and "Authentication" in data["error"]:
                    print(f"   ✅ Correctly rejected: {data['error']}")
                else:
                    print(f"   ❌ Should have been rejected! Got: {data}")
        except Exception as e:
            # FastMCP validates required params before calling - this is expected
            if "api_key" in str(e) and "Missing" in str(e):
                print(f"   ✅ Correctly rejected at validation: api_key is required parameter")
            else:
                print(f"   ❌ Unexpected error: {e}")
        
        # Test 3: Signing tool with WRONG api_key (should fail)
        print("\n--- Test 3: Signing tool with WRONG api_key (should fail) ---")
        result = await client.call_tool("anchor_state_via_pkp", {
            "token_id": 2,
            "state_hash": "0x" + "ab" * 32,
            "state_uri": "test://auth-test",
            "api_key": "wrong-key-12345"
        })
        if result.is_error:
            print(f"   ✅ Correctly rejected (error in response): {result.content}")
        else:
            data = result.data
            if "error" in data and "Authentication" in data["error"]:
                print(f"   ✅ Correctly rejected: {data['error']}")
            else:
                print(f"   ❌ Should have been rejected! Got: {data}")
        
        # Test 4: Signing tool with CORRECT api_key (should succeed to validation)
        print("\n--- Test 4: Signing tool with CORRECT api_key (should pass auth) ---")
        if not MCP_API_KEY:
            print("   ⚠️  MCP_API_KEY not set, skipping test")
        else:
            result = await client.call_tool("anchor_state_via_pkp", {
                "token_id": 2,
                "state_hash": "0x" + "ab" * 32,  # Invalid hash for actual anchoring
                "state_uri": "test://auth-test",
                "api_key": MCP_API_KEY
            })
            if result.is_error:
                print(f"   Result: {result.content}")
            else:
                data = result.data
                if "error" in data and "Authentication" in data["error"]:
                    print(f"   ❌ Auth should have passed! Got: {data['error']}")
                elif "error" in data:
                    # Other errors are fine - auth passed but something else failed
                    print(f"   ✅ Auth passed! (subsequent error: {data['error'][:50]}...)")
                else:
                    print(f"   ✅ Auth passed and operation succeeded!")
        
        print("\n" + "=" * 60)
        print("Authentication tests complete!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_auth())
