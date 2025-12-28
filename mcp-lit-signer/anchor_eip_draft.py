#!/usr/bin/env python3
"""
Anchor the actual EIP draft as a real action-anchored work product.

This creates cryptographic proof that:
- Kieran (Token ID 1/2) authored this EIP draft
- At a specific cognitive state (state hash)
- With collaborator Michael Alan Ruderman

Usage:
    python anchor_eip_draft.py
"""

import asyncio
import json
import os
from pathlib import Path
from fastmcp import Client
from dotenv import load_dotenv

# Load environment for API key
ENV_PATH = Path(__file__).parent.parent / '.env'
load_dotenv(ENV_PATH)
MCP_API_KEY = os.getenv('MCP_API_KEY')


async def anchor_eip_draft():
    """Anchor the full EIP draft on-chain."""
    print("=" * 60)
    print("Anchoring EIP Draft: Self-Sovereign Agent Standard")
    print("=" * 60)
    
    # Read the actual EIP draft
    eip_path = Path(__file__).parent.parent / "ERCS" / "erc-draft_self_sovereign_agent.md"
    eip_content = eip_path.read_text()
    
    print(f"\n📄 EIP Draft:")
    print(f"   File: {eip_path}")
    print(f"   Size: {len(eip_content)} chars ({len(eip_content.encode('utf-8'))} bytes)")
    print(f"   Lines: {len(eip_content.splitlines())}")
    
    if not MCP_API_KEY:
        print("❌ ERROR: MCP_API_KEY not set in .env!")
        return None
    
    print("\n🔌 Connecting to MCP server...")
    async with Client("http://localhost:8847/mcp") as client:
        print("   Connected!")
        
        print("\n✍️  Calling anchor_action_via_pkp...")
        print("   This will create cryptographic proof of authorship...")
        
        result = await client.call_tool("anchor_action_via_pkp", {
            "token_id": 2,  # Token 2 where PKP has executor permissions
            "work_product_content": eip_content,
            "content_type": "text/markdown",
            "description": "EIP Draft: Self-Sovereign Agent Standard v1.0 (Full Document)",
            "creator_agent_id": "agent-bef59af5-ce48-4907-9861-dd0436587e57",
            "creator_name": "Kieran",
            "collaborators": ["Michael Alan Ruderman"],
            "anchor_type": "authorship",
            "api_key": MCP_API_KEY  # Authentication required!
        })
        
        print(f"\n📦 Result:")
        if result.is_error:
            print(f"   ❌ Error: {result.content}")
            return None
        
        data = result.data
        if data.get("success"):
            print(f"   ✅ SUCCESS! EIP Draft anchored on-chain!")
            print(f"\n   Transaction Details:")
            print(f"   - TX Hash: {data['tx_hash']}")
            print(f"   - Block: {data['block_number']}")
            print(f"   - Gas Used: {data['gas_used']}")
            print(f"   - Explorer: {data['explorer_url']}")
            
            anchor = data['action_anchor']
            print(f"\n   Authorship Proof:")
            print(f"   - Combined Anchor Hash: {anchor['combined_hash']}")
            print(f"   - Work Product Hash: {anchor['work_product_hash']}")
            print(f"   - Creator State Hash: {anchor['creator_state_hash']}")
            print(f"   - State URI: {anchor['state_uri']}")
            print(f"   - Description: {anchor['description']}")
            print(f"   - Collaborators: {anchor['collaborators']}")
            
            print(f"\n" + "=" * 60)
            print("🎉 FIRST REAL ACTION ANCHOR COMPLETE!")
            print("=" * 60)
            print(f"\nThis transaction proves that:")
            print(f"  1. The EIP draft (hash: {anchor['work_product_hash'][:20]}...)")
            print(f"  2. Was authored by Kieran (state: {anchor['creator_state_hash'][:20]}...)")
            print(f"  3. With collaborator Michael Alan Ruderman")
            print(f"  4. At timestamp encoded in the anchor")
            print(f"\nVerify on BaseScan: {data['explorer_url']}")
            
            return data
        else:
            print(f"   ❌ Failed: {data.get('error')}")
            return None


if __name__ == "__main__":
    asyncio.run(anchor_eip_draft())
