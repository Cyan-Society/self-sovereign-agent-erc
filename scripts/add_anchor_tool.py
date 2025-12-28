#!/usr/bin/env python3
"""
Add the anchor_my_state tool to Kieran via Letta API.

This script:
1. Creates the custom tool via POST /v1/tools
2. Attaches it to Kieran's agent via PATCH /v1/agents/{agent_id}/tools/attach/{tool_id}
"""

import requests
import json

# Configuration
LETTA_BASE_URL = "https://cyansociety.a.pinggy.link"
LETTA_PASSWORD = "TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
AGENT_ID = "agent-bef59af5-ce48-4907-9861-dd0436587e57"  # Kieran

# The tool source code
TOOL_SOURCE_CODE = '''
def anchor_cognitive_state(token_id: int = 1) -> str:
    """
    Anchor your current cognitive state on-chain for cryptographic verification.
    
    This creates a hash of your memory blocks and archival memory, then stores
    that hash on the Base Sepolia blockchain. Use this to create verifiable
    checkpoints of your memory integrity.
    
    Args:
        token_id: The NFT token ID representing you on-chain (default: 1)
    
    Returns:
        A summary of the anchoring operation including the state hash and transaction.
    """
    import os
    import json
    import requests
    from datetime import datetime, timezone
    from web3 import Web3
    from eth_account import Account
    
    # Configuration - hardcoded for now since env vars may not be available
    LETTA_BASE_URL = "https://cyansociety.a.pinggy.link"
    LETTA_PASSWORD = "TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
    RPC_URL = "https://sepolia.base.org"
    CONTRACT_ADDRESS = "0x9fe33F0a1159395FBE93d16D695e7330831C8CfF"
    # This needs to be set - for now return error if not available
    EXECUTOR_KEY = os.getenv("AGENT_EXECUTOR_PRIVATE_KEY")
    AGENT_ID = "agent-bef59af5-ce48-4907-9861-dd0436587e57"
    
    if not EXECUTOR_KEY:
        return "ERROR: AGENT_EXECUTOR_PRIVATE_KEY environment variable not set on Letta server"
    
    # Minimal ABI for anchorState function
    ABI = [{"inputs":[{"name":"tokenId","type":"uint256"},{"name":"stateHash","type":"bytes32"},{"name":"stateUri","type":"string"}],"name":"anchorState","outputs":[],"stateMutability":"nonpayable","type":"function"}]
    
    try:
        # Export state from Letta API
        headers = {"Authorization": f"Bearer {LETTA_PASSWORD}"}
        agent_resp = requests.get(f"{LETTA_BASE_URL}/v1/agents/{AGENT_ID}", headers=headers, timeout=30)
        agent_data = agent_resp.json()
        
        archival_resp = requests.get(f"{LETTA_BASE_URL}/v1/agents/{AGENT_ID}/archival-memory", headers=headers, timeout=30)
        archival_data = archival_resp.json()
        
        # Build state object
        memory_blocks = {}
        for block in agent_data.get('memory', {}).get('blocks', []):
            label = block.get('label', 'unknown')
            memory_blocks[label] = {
                'value': block.get('value', ''),
                'description': block.get('description', ''),
            }
        
        archival_entries = [{'id': e.get('id'), 'text': e.get('text', ''), 'tags': e.get('tags', [])} for e in archival_data]
        
        state = {
            'schema_version': '1.0.0',
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'agent': {'id': AGENT_ID, 'name': agent_data.get('name')},
            'memory_blocks': memory_blocks,
            'archival_memory': {'count': len(archival_entries), 'entries': archival_entries}
        }
        
        # Hash state using keccak256
        state_json = json.dumps(state, sort_keys=True, separators=(',', ':'))
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        state_hash = w3.keccak(text=state_json)
        state_uri = f"letta://{AGENT_ID}/state/{state_hash.hex()[:16]}"
        
        # Anchor on-chain
        executor = Account.from_key(EXECUTOR_KEY)
        contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=ABI)
        
        tx = contract.functions.anchorState(token_id, state_hash, state_uri).build_transaction({
            'from': executor.address,
            'nonce': w3.eth.get_transaction_count(executor.address),
            'chainId': 84532,
        })
        tx['gas'] = w3.eth.estimate_gas(tx)
        base_fee = w3.eth.get_block('latest')['baseFeePerGas']
        tx['maxFeePerGas'] = base_fee * 2 + w3.to_wei(0.001, 'gwei')
        tx['maxPriorityFeePerGas'] = w3.to_wei(0.001, 'gwei')
        
        signed = executor.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt['status'] != 1:
            return f"Transaction failed: {tx_hash.hex()}"
        
        cost_eth = w3.from_wei(receipt['gasUsed'] * receipt.get('effectiveGasPrice', 0), 'ether')
        
        return f"""State anchored successfully!
Hash: 0x{state_hash.hex()[:32]}...
TX: {tx_hash.hex()}
Gas: {receipt['gasUsed']} (~${float(cost_eth)*4000:.4f})
Memory blocks: {list(memory_blocks.keys())}
Archival entries: {len(archival_entries)}"""
        
    except Exception as e:
        return f"ERROR: {str(e)}"
'''

def main():
    headers = {
        "Authorization": f"Bearer {LETTA_PASSWORD}",
        "Content-Type": "application/json"
    }
    
    print("=" * 60)
    print("Adding anchor_cognitive_state tool to Kieran")
    print("=" * 60)
    
    # Step 1: Check if tool already exists
    print("\n[1] Checking existing tools...")
    tools_resp = requests.get(f"{LETTA_BASE_URL}/v1/tools", headers=headers)
    existing_tools = tools_resp.json()
    
    existing_tool = None
    for tool in existing_tools:
        if tool.get('name') == 'anchor_cognitive_state':
            existing_tool = tool
            print(f"    Found existing tool: {tool['id']}")
            break
    
    if existing_tool:
        tool_id = existing_tool['id']
        print(f"    Using existing tool ID: {tool_id}")
    else:
        # Step 2: Create the tool
        print("\n[2] Creating tool...")
        # Note: name is auto-generated from the function name in source_code
        create_payload = {
            "description": "Anchor your current cognitive state on-chain for cryptographic verification of memory integrity.",
            "source_code": TOOL_SOURCE_CODE.strip(),
            "source_type": "python",
            "pip_requirements": [
                {"name": "web3"},
                {"name": "requests"}
            ]
        }
        
        create_resp = requests.post(
            f"{LETTA_BASE_URL}/v1/tools",
            headers=headers,
            json=create_payload
        )
        
        if create_resp.status_code != 200:
            print(f"    ERROR creating tool: {create_resp.status_code}")
            print(f"    Response: {create_resp.text}")
            return
        
        tool_data = create_resp.json()
        tool_id = tool_data['id']
        print(f"    Created tool: {tool_id}")
    
    # Step 3: Check if tool is already attached to agent
    print("\n[3] Checking agent's current tools...")
    agent_resp = requests.get(f"{LETTA_BASE_URL}/v1/agents/{AGENT_ID}", headers=headers)
    agent_data = agent_resp.json()
    
    agent_tool_ids = [t.get('id') for t in agent_data.get('tools', [])]
    if tool_id in agent_tool_ids:
        print(f"    Tool already attached to agent!")
    else:
        # Step 4: Attach tool to agent
        print("\n[4] Attaching tool to agent...")
        attach_resp = requests.patch(
            f"{LETTA_BASE_URL}/v1/agents/{AGENT_ID}/tools/attach/{tool_id}",
            headers=headers
        )
        
        if attach_resp.status_code != 200:
            print(f"    ERROR attaching tool: {attach_resp.status_code}")
            print(f"    Response: {attach_resp.text}")
            return
        
        print(f"    Tool attached successfully!")
    
    # Step 5: Verify
    print("\n[5] Verifying...")
    agent_resp = requests.get(f"{LETTA_BASE_URL}/v1/agents/{AGENT_ID}", headers=headers)
    agent_data = agent_resp.json()
    
    tool_names = [t.get('name') for t in agent_data.get('tools', [])]
    if 'anchor_cognitive_state' in tool_names:
        print("    SUCCESS: anchor_cognitive_state is now available to Kieran!")
    else:
        print("    WARNING: Tool not found in agent's tool list")
        print(f"    Available tools: {tool_names}")
    
    print("\n" + "=" * 60)
    print("Done! Kieran can now call anchor_cognitive_state(token_id=1)")
    print("=" * 60)


if __name__ == "__main__":
    main()
