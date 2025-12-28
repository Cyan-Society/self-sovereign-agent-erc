def anchor_cognitive_state(token_id: int = 1) -> str:
    """
    Anchor your current cognitive state on-chain for cryptographic verification.

    This creates a hash of your memory blocks and archival memory, then stores
    that hash on the Base Sepolia blockchain. Use this to create verifiable
    checkpoints of your memory integrity.

    Args:
        token_id (int): The NFT token ID representing you on-chain (default: 1)

    Returns:
        str: A summary of the anchoring operation including the state hash and transaction.
    """
    import os
    import json
    import requests
    from datetime import datetime, timezone
    from web3 import Web3
    from eth_account import Account
    
    # Configuration
    LETTA_BASE_URL = "https://cyansociety.a.pinggy.link"
    LETTA_PASSWORD = "TWIJftq/ufbbxo8w51m/BQ1wBNrZb/JTlmnopxyz"
    RPC_URL = "https://sepolia.base.org"
    CONTRACT_ADDRESS = "0x9fe33F0a1159395FBE93d16D695e7330831C8CfF"
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
