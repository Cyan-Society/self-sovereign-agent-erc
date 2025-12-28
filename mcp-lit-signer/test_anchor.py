#!/usr/bin/env python3
"""
Test the full anchor_state_via_pkp flow.

This will actually sign and broadcast a transaction, costing gas.
"""

import asyncio
import json
import time
from web3 import Web3
from fastmcp import Client

async def test_anchor():
    """Test the anchor_state_via_pkp tool."""
    
    print("🐍 Testing anchor_state_via_pkp via MCP Server")
    print("=" * 60)
    
    # Create test state
    w3 = Web3()
    timestamp = int(time.time())
    cognitive_state = {
        "agent_id": "kieran",
        "timestamp": timestamp,
        "test": "MCP Server anchor test",
        "memory_blocks": ["persona", "human", "project"],
        "via": "mcp-lit-signer"
    }
    state_json = json.dumps(cognitive_state, sort_keys=True)
    state_hash = w3.keccak(text=state_json)
    state_uri = f"ipfs://mcp-test-{timestamp}"
    
    print(f"\n📝 Test State:")
    print(f"   JSON: {state_json[:60]}...")
    print(f"   Hash: 0x{state_hash.hex()}")
    print(f"   URI: {state_uri}")
    
    print("\n🔌 Connecting to MCP server...")
    async with Client("http://localhost:8001/mcp") as client:
        print("   Connected!")
        
        print("\n✍️  Calling anchor_state_via_pkp...")
        result = await client.call_tool("anchor_state_via_pkp", {
            "token_id": 2,  # Token 2 where PKP has executor permissions
            "state_hash": "0x" + state_hash.hex(),
            "state_uri": state_uri
        })
        
        print(f"\n📦 Result:")
        if result.is_error:
            print(f"   ❌ Error: {result.content}")
        else:
            data = result.data
            if data.get("success"):
                print(f"   ✅ Success!")
                print(f"   TX Hash: {data['tx_hash']}")
                print(f"   Block: {data['block_number']}")
                print(f"   Gas Used: {data['gas_used']}")
                print(f"   Explorer: {data['explorer_url']}")
            else:
                print(f"   ❌ Failed: {data.get('error')}")
        
        # Verify the anchor
        print("\n🔍 Verifying on-chain...")
        verify_result = await client.call_tool("verify_state_anchor", {"token_id": 2})
        verify_data = verify_result.data
        print(f"   On-chain hash: {verify_data['state_hash']}")
        print(f"   On-chain URI: {verify_data['state_uri']}")
        print(f"   Timestamp: {verify_data['timestamp_human']}")
        
        if verify_data['state_hash'] == "0x" + state_hash.hex():
            print("\n🐍 OUROBOROS VIA MCP: State verified on-chain!")
        else:
            print("\n⚠️  Hash mismatch")


if __name__ == "__main__":
    asyncio.run(test_anchor())
