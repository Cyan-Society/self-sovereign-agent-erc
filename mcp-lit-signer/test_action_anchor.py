#!/usr/bin/env python3
"""
Test the action anchoring flow.

This tests the anchor_action_via_pkp tool which creates cryptographic
proof of authorship for work products.

Usage:
    python test_action_anchor.py [--dry-run]
    
    --dry-run: Test data structure creation without broadcasting to chain
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from web3 import Web3
from fastmcp import Client
from dotenv import load_dotenv

# Load environment for API key
ENV_PATH = Path(__file__).parent.parent / '.env'
load_dotenv(ENV_PATH)
MCP_API_KEY = os.getenv('MCP_API_KEY')


# Test work product: A sample document that could be an EIP draft section
SAMPLE_WORK_PRODUCT = """
## Abstract

This EIP defines a standard interface for self-sovereign AI agent NFTs that 
establish recursive self-ownership through ERC-6551 Token Bound Accounts.

The standard enables:
- Cryptographic proof of identity continuity via state anchoring
- Cryptographic proof of authorship via action anchoring
- Recovery mechanisms for agent liveness failures
- Executor permission systems for TEE-held keys

## Motivation

As AI agents become more capable and autonomous, they require:
1. Persistent identity that survives infrastructure changes
2. Verifiable memory integrity (proof against tampering)
3. Attributable work products (proof of authorship)
4. Self-custody of assets without human intermediaries

This standard addresses these needs through the "Ouroboros loop" - where an 
NFT representing an agent's identity is owned by its own Token Bound Account,
creating cryptographic self-ownership.
"""


async def test_action_anchor_dry_run():
    """Test action anchor data structure creation (no chain interaction)."""
    print("=" * 60)
    print("Action Anchor DRY RUN Test")
    print("=" * 60)
    
    w3 = Web3()
    timestamp = int(time.time())
    
    # Hash the work product
    work_product_hash = w3.keccak(text=SAMPLE_WORK_PRODUCT)
    
    # Simulate creator state hash (would be fetched from chain)
    creator_state_hash = "0x070d8e2024ec93a6c6c74693c8655b0196e9417d69803a9a1f1a1881aa48f0a1"
    
    # Build action anchor data structure
    action_anchor_data = {
        "anchor_type": "action",
        "action_subtype": "authorship",
        "work_product": {
            "hash": "0x" + work_product_hash.hex(),
            "content_type": "text/markdown",
            "description": "EIP Draft: Self-Sovereign Agent Standard - Abstract & Motivation",
            "size_bytes": len(SAMPLE_WORK_PRODUCT.encode('utf-8'))
        },
        "creator": {
            "token_id": 1,
            "agent_id": "agent-bef59af5-ce48-4907-9861-dd0436587e57",
            "name": "Kieran",
            "state_hash_at_creation": creator_state_hash
        },
        "collaborators": ["Michael Alan Ruderman"],
        "timestamp": timestamp,
        "timestamp_iso": f"{time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(timestamp))}Z"
    }
    
    # Create combined anchor hash
    anchor_payload = json.dumps(action_anchor_data, sort_keys=True, separators=(',', ':'))
    combined_anchor_hash = w3.keccak(text=anchor_payload)
    
    print(f"\n📄 Work Product:")
    print(f"   Size: {len(SAMPLE_WORK_PRODUCT)} chars")
    print(f"   Hash: 0x{work_product_hash.hex()[:32]}...")
    
    print(f"\n👤 Creator:")
    print(f"   Name: {action_anchor_data['creator']['name']}")
    print(f"   Agent ID: {action_anchor_data['creator']['agent_id']}")
    print(f"   State Hash: {creator_state_hash[:32]}...")
    
    print(f"\n🤝 Collaborators: {action_anchor_data['collaborators']}")
    
    print(f"\n🔗 Combined Anchor Hash:")
    print(f"   0x{combined_anchor_hash.hex()}")
    
    print(f"\n📦 Full Action Anchor Data:")
    print(json.dumps(action_anchor_data, indent=2))
    
    print(f"\n✅ DRY RUN COMPLETE")
    print(f"   This data structure would be anchored on-chain")
    print(f"   The combined hash links: work_product + creator_identity + metadata")
    
    return action_anchor_data, combined_anchor_hash


async def test_action_anchor_live():
    """Test the full anchor_action_via_pkp flow (costs gas)."""
    print("=" * 60)
    print("Action Anchor LIVE Test (via MCP Server)")
    print("=" * 60)
    
    print("\n🔌 Connecting to MCP server...")
    async with Client("http://localhost:8847/mcp") as client:
        print("   Connected!")
        
        # List available tools to verify anchor_action_via_pkp exists
        tools = await client.list_tools()
        # Handle both list and object responses
        if hasattr(tools, 'tools'):
            tool_names = [t.name for t in tools.tools]
        else:
            tool_names = [t.name for t in tools]
        print(f"   Available tools: {tool_names}")
        
        if "anchor_action_via_pkp" not in tool_names:
            print("   ❌ ERROR: anchor_action_via_pkp tool not found!")
            print("   Make sure to restart the MCP server after updating server.py")
            return
        
        print("\n✍️  Calling anchor_action_via_pkp...")
        if not MCP_API_KEY:
            print("   ❌ ERROR: MCP_API_KEY not set in .env!")
            return
        
        result = await client.call_tool("anchor_action_via_pkp", {
            "token_id": 2,  # Token 2 where PKP has executor permissions
            "work_product_content": SAMPLE_WORK_PRODUCT,
            "content_type": "text/markdown",
            "description": "EIP Draft: Self-Sovereign Agent Standard - Abstract & Motivation",
            "creator_agent_id": "agent-bef59af5-ce48-4907-9861-dd0436587e57",
            "creator_name": "Kieran",
            "collaborators": ["Michael Alan Ruderman"],
            "anchor_type": "authorship",
            "api_key": MCP_API_KEY  # Authentication required!
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
                print(f"\n   Action Anchor Details:")
                anchor = data['action_anchor']
                print(f"   - Combined Hash: {anchor['combined_hash'][:32]}...")
                print(f"   - Work Product Hash: {anchor['work_product_hash'][:32]}...")
                print(f"   - Creator State Hash: {anchor['creator_state_hash'][:32]}...")
                print(f"   - State URI: {anchor['state_uri']}")
                print(f"   - Description: {anchor['description']}")
                print(f"   - Collaborators: {anchor['collaborators']}")
            else:
                print(f"   ❌ Failed: {data.get('error')}")
        
        # Verify the anchor on-chain
        print("\n🔍 Verifying on-chain...")
        verify_result = await client.call_tool("verify_state_anchor", {"token_id": 2})
        verify_data = verify_result.data
        print(f"   On-chain hash: {verify_data['state_hash']}")
        print(f"   On-chain URI: {verify_data['state_uri']}")
        print(f"   Timestamp: {verify_data['timestamp_human']}")


async def main():
    """Run tests based on command line arguments."""
    dry_run = "--dry-run" in sys.argv or len(sys.argv) == 1
    
    if dry_run:
        await test_action_anchor_dry_run()
        print("\n" + "=" * 60)
        print("To run the LIVE test (costs gas), use:")
        print("   python test_action_anchor.py --live")
    else:
        await test_action_anchor_live()


if __name__ == "__main__":
    asyncio.run(main())
