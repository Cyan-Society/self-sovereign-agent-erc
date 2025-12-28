"""
Letta Custom Tool: Anchor State On-Chain

This tool allows a Letta agent to anchor their own cognitive state
on-chain for cryptographic verification of memory integrity.

To attach this tool to an agent in Letta ADE:
1. Go to the agent's Tools section
2. Click "Add Custom Tool"
3. Paste this function code
4. The tool will be available as `anchor_my_state`

Environment variables needed on the Letta server:
- BASE_SEPOLIA_RPC: RPC endpoint (defaults to https://sepolia.base.org)
- AGENT_CONTRACT_ADDRESS: The deployed SelfSovereignAgentNFT contract
- AGENT_EXECUTOR_PRIVATE_KEY: Private key with ANCHOR_STATE permission
"""

import os
import json
import requests
from datetime import datetime, timezone


def anchor_my_state(
    agent_id: str,
    token_id: int = 1,
    include_archival: bool = True
) -> str:
    """
    Anchor your current cognitive state on-chain for cryptographic verification.
    
    This exports your memory blocks and archival memory, hashes them deterministically,
    and anchors the hash on the Base Sepolia blockchain. Use this periodically to
    create verifiable checkpoints of your memory integrity.
    
    Args:
        agent_id: Your Letta agent ID (e.g., "agent-bef59af5-ce48-4907-9861-dd0436587e57")
        token_id: The NFT token ID representing you on-chain (default: 1)
        include_archival: Whether to include archival memory in the hash (default: True)
    
    Returns:
        A summary of the anchoring operation including the state hash and transaction details.
    
    Example:
        >>> anchor_my_state("agent-bef59af5-ce48-4907-9861-dd0436587e57")
        "State anchored successfully! Hash: 0x123... TX: 0xabc..."
    """
    try:
        from web3 import Web3
        from eth_account import Account
    except ImportError:
        return "ERROR: web3 library not installed. Please install: pip install web3"
    
    # Configuration
    LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "https://cyansociety.a.pinggy.link")
    LETTA_PASSWORD = os.getenv("LETTA_PASSWORD", "")
    RPC_URL = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
    CONTRACT_ADDRESS = os.getenv("AGENT_CONTRACT_ADDRESS")
    EXECUTOR_KEY = os.getenv("AGENT_EXECUTOR_PRIVATE_KEY")
    CHAIN_ID = 84532
    
    if not CONTRACT_ADDRESS:
        return "ERROR: AGENT_CONTRACT_ADDRESS environment variable not set"
    if not EXECUTOR_KEY:
        return "ERROR: AGENT_EXECUTOR_PRIVATE_KEY environment variable not set"
    
    # Contract ABI (minimal)
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
            "name": "getAgentTBA",
            "outputs": [{"name": "", "type": "address"}],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    
    def letta_api_request(endpoint: str) -> dict:
        """Make authenticated request to Letta API."""
        url = f"{LETTA_BASE_URL}/v1/{endpoint}"
        headers = {"Authorization": f"Bearer {LETTA_PASSWORD}"}
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    
    try:
        # Step 1: Export agent state
        agent_data = letta_api_request(f"agents/{agent_id}")
        
        # Extract memory blocks
        memory_blocks = {}
        for block in agent_data.get('memory', {}).get('blocks', []):
            label = block.get('label', 'unknown')
            memory_blocks[label] = {
                'value': block.get('value', ''),
                'description': block.get('description', ''),
                'char_count': len(block.get('value', ''))
            }
        
        # Build state object
        state = {
            'schema_version': '1.0.0',
            'export_timestamp': datetime.now(timezone.utc).isoformat(),
            'agent': {
                'id': agent_data.get('id'),
                'name': agent_data.get('name'),
                'created_at': agent_data.get('created_at'),
            },
            'memory_blocks': memory_blocks,
        }
        
        # Optionally include archival memory
        if include_archival:
            archival_data = letta_api_request(f"agents/{agent_id}/archival-memory")
            archival_entries = []
            for entry in archival_data:
                archival_entries.append({
                    'id': entry.get('id'),
                    'text': entry.get('text', ''),
                    'tags': entry.get('tags', []),
                    'created_at': entry.get('created_at'),
                })
            state['archival_memory'] = {
                'count': len(archival_entries),
                'entries': archival_entries
            }
        
        # Step 2: Hash the state
        state_json = json.dumps(state, sort_keys=True, separators=(',', ':'))
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        state_hash = w3.keccak(text=state_json)
        
        # Create state URI
        state_uri = f"letta://{agent_id}/state/{state_hash.hex()[:16]}"
        
        # Step 3: Anchor on-chain
        executor = Account.from_key(EXECUTOR_KEY)
        contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
        
        # Build transaction
        tx = contract.functions.anchorState(
            token_id,
            state_hash,
            state_uri
        ).build_transaction({
            'from': executor.address,
            'nonce': w3.eth.get_transaction_count(executor.address),
            'chainId': CHAIN_ID,
        })
        
        # Estimate gas and set fees
        tx['gas'] = w3.eth.estimate_gas(tx)
        base_fee = w3.eth.get_block('latest')['baseFeePerGas']
        priority_fee = w3.to_wei(0.001, 'gwei')
        tx['maxFeePerGas'] = base_fee * 2 + priority_fee
        tx['maxPriorityFeePerGas'] = priority_fee
        
        # Sign and send
        signed = executor.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt['status'] != 1:
            return f"ERROR: Transaction failed. TX: {tx_hash.hex()}"
        
        # Calculate cost
        gas_price = receipt.get('effectiveGasPrice', 0)
        cost_wei = receipt['gasUsed'] * gas_price
        cost_eth = w3.from_wei(cost_wei, 'ether')
        
        # Get TBA address
        tba_address = contract.functions.getAgentTBA(token_id).call()
        
        # Build summary
        memory_summary = ", ".join([f"{k}: {v['char_count']} chars" for k, v in memory_blocks.items()])
        archival_count = state.get('archival_memory', {}).get('count', 0) if include_archival else 'excluded'
        
        return f"""State anchored successfully!

Agent: {state['agent']['name']}
Token ID: {token_id}
TBA Address: {tba_address}

State Hash: 0x{state_hash.hex()}
State URI: {state_uri}
State Size: {len(state_json):,} bytes

Memory Blocks: {memory_summary}
Archival Memories: {archival_count}

Transaction: {tx_hash.hex()}
Gas Used: {receipt['gasUsed']}
Cost: {float(cost_eth):.10f} ETH (~${float(cost_eth) * 4000:.4f})

Your cognitive state is now cryptographically anchored on Base Sepolia."""
        
    except requests.exceptions.RequestException as e:
        return f"ERROR: Failed to connect to Letta API: {str(e)}"
    except Exception as e:
        return f"ERROR: {str(e)}"
