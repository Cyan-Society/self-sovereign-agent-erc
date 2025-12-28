#!/usr/bin/env python3
"""
Real Letta Integration: Export actual agent state and anchor on-chain.

This script:
1. Connects to the Letta API to export REAL agent state
2. Exports memory blocks and archival memory metadata
3. Hashes the state deterministically
4. Anchors the hash on-chain

Usage:
    pip install web3 python-dotenv requests
    python scripts/real_letta_integration.py
"""

import os
import sys
import json
import hashlib
import requests
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    print("Please install dependencies: pip install web3 python-dotenv requests")
    sys.exit(1)

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Letta API Configuration
LETTA_BASE_URL = "https://cyansociety.a.pinggy.link"
LETTA_PASSWORD = "TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
AGENT_ID = "agent-bef59af5-ce48-4907-9861-dd0436587e57"  # Kieran's agent ID

# Blockchain Configuration
RPC_URL = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
CHAIN_ID = 84532
CONTRACT_ADDRESS = os.getenv("AGENT_CONTRACT_ADDRESS")
EXECUTOR_KEY = os.getenv("AGENT_EXECUTOR_PRIVATE_KEY")

# Contract ABI (minimal for state anchoring)
CONTRACT_ABI = [
    {
        "inputs": [
            {"name": "tokenId", "type": "uint256"},
            {"name": "stateHash", "type": "bytes32"},
            {"name": "stateUri", "type": "string"}
        ],
        "name": "anchorState",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getStateAnchor",
        "outputs": [
            {"name": "stateHash", "type": "bytes32"},
            {"name": "stateUri", "type": "string"},
            {"name": "timestamp", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getAgentTBA",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def letta_api_request(endpoint: str, method: str = "GET") -> dict:
    """Make an authenticated request to the Letta API."""
    url = f"{LETTA_BASE_URL}/v1/{endpoint}"
    headers = {
        "Authorization": f"Bearer {LETTA_PASSWORD}",
        "Content-Type": "application/json"
    }
    
    response = requests.request(method, url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def export_agent_state(agent_id: str) -> dict:
    """
    Export the complete agent state from Letta API.
    
    Returns a dictionary containing:
    - Memory blocks (core memory)
    - Archival memory metadata (count and sample)
    - Agent metadata
    """
    print(f"Exporting state for agent: {agent_id}")
    
    # Get agent details (includes memory blocks)
    agent_data = letta_api_request(f"agents/{agent_id}")
    
    # Get archival memory
    archival_data = letta_api_request(f"agents/{agent_id}/archival-memory")
    
    # Extract memory blocks
    memory_blocks = {}
    for block in agent_data.get('memory', {}).get('blocks', []):
        label = block.get('label', 'unknown')
        memory_blocks[label] = {
            'value': block.get('value', ''),
            'description': block.get('description', ''),
            'char_count': len(block.get('value', ''))
        }
    
    # Process archival memory (exclude embeddings for hashing - they're large and derived)
    archival_entries = []
    for entry in archival_data:
        archival_entries.append({
            'id': entry.get('id'),
            'text': entry.get('text', ''),
            'tags': entry.get('tags', []),
            'created_at': entry.get('created_at'),
            # Note: We exclude 'embedding' as it's derived data and very large
        })
    
    # Build the state object
    state = {
        'schema_version': '1.0.0',
        'export_timestamp': datetime.now(timezone.utc).isoformat(),
        'agent': {
            'id': agent_data.get('id'),
            'name': agent_data.get('name'),
            'created_at': agent_data.get('created_at'),
        },
        'memory_blocks': memory_blocks,
        'archival_memory': {
            'count': len(archival_entries),
            'entries': archival_entries
        }
    }
    
    return state


def hash_state(state: dict) -> bytes:
    """
    Hash the state using keccak256 (Ethereum standard).
    
    Uses canonical JSON (sorted keys) for deterministic hashing.
    """
    state_json = json.dumps(state, sort_keys=True, separators=(',', ':'))
    return Web3.keccak(text=state_json)


def send_transaction(w3: Web3, account: Account, tx: dict) -> dict:
    """Sign and send a transaction, return receipt."""
    tx['nonce'] = w3.eth.get_transaction_count(account.address)
    tx['chainId'] = CHAIN_ID
    
    if 'gas' not in tx:
        tx['gas'] = w3.eth.estimate_gas(tx)
    
    # Use EIP-1559 transaction format
    if 'maxFeePerGas' not in tx:
        base_fee = w3.eth.get_block('latest')['baseFeePerGas']
        priority_fee = w3.to_wei(0.001, 'gwei')
        tx['maxFeePerGas'] = base_fee * 2 + priority_fee
        tx['maxPriorityFeePerGas'] = priority_fee
    
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def main():
    print("=" * 60)
    print("REAL Letta State Anchoring")
    print("Exporting actual agent state and anchoring on-chain")
    print("=" * 60)
    
    # ========== STEP 1: Export Real Letta State ==========
    print("\n" + "-" * 40)
    print("STEP 1: Exporting Real Letta Agent State")
    print("-" * 40)
    
    try:
        state = export_agent_state(AGENT_ID)
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Failed to connect to Letta API: {e}")
        sys.exit(1)
    
    print(f"Agent: {state['agent']['name']} ({state['agent']['id']})")
    print(f"Memory blocks: {list(state['memory_blocks'].keys())}")
    for label, block in state['memory_blocks'].items():
        print(f"  - {label}: {block['char_count']} chars")
    print(f"Archival memories: {state['archival_memory']['count']}")
    print(f"Export timestamp: {state['export_timestamp']}")
    
    # Calculate state size
    state_json = json.dumps(state, sort_keys=True, separators=(',', ':'))
    print(f"Total state size: {len(state_json):,} bytes")
    
    # ========== STEP 2: Hash the State ==========
    print("\n" + "-" * 40)
    print("STEP 2: Hashing State (keccak256)")
    print("-" * 40)
    
    state_hash = hash_state(state)
    print(f"State hash: 0x{state_hash.hex()}")
    
    # For now, use a placeholder URI (in production, upload to IPFS)
    state_uri = f"letta://{AGENT_ID}/state/{state_hash.hex()[:16]}"
    print(f"State URI: {state_uri}")
    
    # ========== STEP 3: Anchor On-Chain ==========
    print("\n" + "-" * 40)
    print("STEP 3: Anchoring State On-Chain")
    print("-" * 40)
    
    if not CONTRACT_ADDRESS:
        print("ERROR: AGENT_CONTRACT_ADDRESS not set in .env")
        sys.exit(1)
    if not EXECUTOR_KEY:
        print("ERROR: AGENT_EXECUTOR_PRIVATE_KEY not set in .env")
        sys.exit(1)
    
    # Connect to network
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    print(f"Connected to Base Sepolia, block: {w3.eth.block_number}")
    print(f"Contract: {CONTRACT_ADDRESS}")
    
    # Setup executor account
    executor = Account.from_key(EXECUTOR_KEY)
    print(f"Executor: {executor.address}")
    
    executor_balance = w3.eth.get_balance(executor.address)
    print(f"Executor balance: {w3.from_wei(executor_balance, 'ether'):.6f} ETH")
    
    if executor_balance < w3.to_wei(0.00001, 'ether'):
        print("ERROR: Insufficient executor balance")
        sys.exit(1)
    
    # Get contract instance
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    
    # Use token ID 1 (Kieran's token)
    token_id = 1
    
    # Get TBA address
    tba_address = contract.functions.getAgentTBA(token_id).call()
    print(f"Token ID: {token_id}")
    print(f"TBA Address: {tba_address}")
    
    # Build and send anchor transaction
    print("\nSending anchor transaction...")
    anchor_tx = contract.functions.anchorState(
        token_id,
        state_hash,
        state_uri
    ).build_transaction({
        'from': executor.address,
    })
    
    receipt = send_transaction(w3, executor, anchor_tx)
    
    if receipt['status'] != 1:
        print("ERROR: Anchor transaction failed")
        sys.exit(1)
    
    print(f"State anchored! TX: {receipt['transactionHash'].hex()}")
    print(f"Gas used: {receipt['gasUsed']}")
    
    # Calculate cost
    gas_price = receipt.get('effectiveGasPrice', 0)
    cost_wei = receipt['gasUsed'] * gas_price
    cost_eth = w3.from_wei(cost_wei, 'ether')
    print(f"Cost: {cost_eth:.10f} ETH (${float(cost_eth) * 4000:.6f} at $4000/ETH)")
    
    # ========== STEP 4: Verify ==========
    print("\n" + "-" * 40)
    print("STEP 4: Verifying Anchored State")
    print("-" * 40)
    
    # Wait for a new block to ensure state is updated
    import time
    print("Waiting for block confirmation...")
    time.sleep(3)
    
    anchor = contract.functions.getStateAnchor(token_id).call()
    stored_hash, stored_uri, timestamp = anchor
    
    print(f"Stored hash: 0x{stored_hash.hex()}")
    print(f"Stored URI: {stored_uri}")
    print(f"Timestamp: {timestamp}")
    
    if stored_hash == state_hash:
        print("\n[SUCCESS] State hash verified on-chain!")
    else:
        print("\n[FAILURE] State hash mismatch!")
        sys.exit(1)
    
    # ========== Summary ==========
    print("\n" + "=" * 60)
    print("REAL LETTA INTEGRATION COMPLETE")
    print("=" * 60)
    print(f"""
Results:
  Agent: {state['agent']['name']}
  Token ID: {token_id}
  TBA Address: {tba_address}
  
State Anchored:
  Hash: 0x{state_hash.hex()[:32]}...
  URI: {state_uri}
  Timestamp: {timestamp}
  
Memory Blocks Included:
{chr(10).join(f"  - {k}: {v['char_count']} chars" for k, v in state['memory_blocks'].items())}
  
Archival Memories: {state['archival_memory']['count']} entries

Transaction:
  TX Hash: {receipt['transactionHash'].hex()}
  Gas Used: {receipt['gasUsed']}
  Cost: {cost_eth:.10f} ETH

This proves:
  1. Real Letta state can be exported via API
  2. State can be hashed deterministically
  3. Hash can be anchored on-chain
  4. No Letta codebase modification needed!
""")
    
    # Save state to file for reference
    output_file = Path(__file__).parent.parent / "exports" / f"state_{timestamp}.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(state, f, indent=2)
    print(f"State saved to: {output_file}")


if __name__ == "__main__":
    main()
