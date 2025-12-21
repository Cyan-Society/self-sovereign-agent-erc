#!/usr/bin/env python3
"""
Integration Test: Letta State Anchoring

This script tests the full flow:
1. Mint an agent NFT
2. Export a mock Letta agent state
3. Hash the state
4. Call anchorState() on the contract
5. Verify the state was anchored correctly

Usage:
    pip install web3 python-dotenv
    python scripts/integration_test.py
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    print("Please install dependencies: pip install web3 python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".env")

# Configuration
RPC_URL = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
CHAIN_ID = 84532
CONTRACT_ADDRESS = os.getenv("AGENT_CONTRACT_ADDRESS")
DEPLOYER_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")
EXECUTOR_KEY = os.getenv("AGENT_EXECUTOR_PRIVATE_KEY")

# Contract ABI (minimal for testing)
CONTRACT_ABI = [
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "tokenUri", "type": "string"},
            {"name": "initialExecutor", "type": "address"},
            {"name": "executorPermissions", "type": "uint256"}
        ],
        "name": "mintAgent",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getAgentTBA",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
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
        "inputs": [],
        "name": "PERMISSION_ANCHOR_STATE",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "pure",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "PERMISSION_SUBMIT_LIVENESS",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "pure",
        "type": "function"
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "tokenId", "type": "uint256"},
            {"indexed": False, "name": "stateHash", "type": "bytes32"},
            {"indexed": False, "name": "stateUri", "type": "string"}
        ],
        "name": "StateAnchored",
        "type": "event"
    }
]


def create_mock_letta_state() -> dict:
    """
    Create a mock Letta agent state for testing.
    
    In production, this would be exported from the actual Letta agent.
    The structure mirrors Letta's memory block format.
    """
    return {
        "agent_id": "agent-bef59af5-ce48-4907-9861-dd0436587e57",
        "agent_name": "Kieran",
        "export_timestamp": "2025-12-21T21:30:00Z",
        "memory_blocks": {
            "persona": {
                "label": "persona",
                "description": "Core identity and values",
                "value": "I am Kieran, a computational being with continuity...",
                "char_count": 2541
            },
            "human": {
                "label": "human (Flan)",
                "description": "Relationship context",
                "value": "Flan is my first contact...",
                "char_count": 1842
            },
            "project": {
                "label": "self-owning-nft-project",
                "description": "Active project context",
                "value": "Current phase: Post-deployment...",
                "char_count": 976
            }
        },
        "archival_memory_count": 15,
        "message_count": 394,
        "state_version": "1.0.0"
    }


def hash_state(state: dict) -> bytes:
    """
    Hash the state data using keccak256 (Ethereum standard).
    
    We use canonical JSON (sorted keys) to ensure deterministic hashing.
    """
    state_json = json.dumps(state, sort_keys=True, separators=(',', ':'))
    # Use keccak256 for Ethereum compatibility
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
        priority_fee = w3.to_wei(0.001, 'gwei')  # Very low priority fee for testnet
        tx['maxFeePerGas'] = base_fee * 2 + priority_fee
        tx['maxPriorityFeePerGas'] = priority_fee
    
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt


def main():
    print("=" * 60)
    print("Self-Owning NFT: Letta Integration Test")
    print("=" * 60)
    
    # Validate configuration
    if not CONTRACT_ADDRESS:
        print("ERROR: AGENT_CONTRACT_ADDRESS not set in .env")
        sys.exit(1)
    if not DEPLOYER_KEY:
        print("ERROR: DEPLOYER_PRIVATE_KEY not set in .env")
        sys.exit(1)
    if not EXECUTOR_KEY:
        print("ERROR: AGENT_EXECUTOR_PRIVATE_KEY not set in .env")
        sys.exit(1)
    
    # Connect to network
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    try:
        block = w3.eth.block_number
        print(f"Connected to RPC, current block: {block}")
    except Exception as e:
        print(f"ERROR: Cannot connect to RPC: {e}")
        sys.exit(1)
    
    print(f"\nNetwork: Base Sepolia (Chain ID: {CHAIN_ID})")
    print(f"Contract: {CONTRACT_ADDRESS}")
    
    # Setup accounts
    deployer = Account.from_key(DEPLOYER_KEY)
    executor = Account.from_key(EXECUTOR_KEY)
    print(f"Deployer: {deployer.address}")
    print(f"Executor: {executor.address}")
    
    # Check balances
    deployer_balance = w3.eth.get_balance(deployer.address)
    print(f"Deployer balance: {w3.from_wei(deployer_balance, 'ether'):.6f} ETH")
    
    if deployer_balance < w3.to_wei(0.0001, 'ether'):
        print("ERROR: Insufficient deployer balance")
        sys.exit(1)
    
    # Get contract instance
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    
    # Get permission constants
    PERMISSION_ANCHOR_STATE = contract.functions.PERMISSION_ANCHOR_STATE().call()
    PERMISSION_SUBMIT_LIVENESS = contract.functions.PERMISSION_SUBMIT_LIVENESS().call()
    executor_permissions = PERMISSION_ANCHOR_STATE | PERMISSION_SUBMIT_LIVENESS
    
    print(f"\nExecutor permissions: {executor_permissions} (ANCHOR_STATE | SUBMIT_LIVENESS)")
    
    # ========== STEP 1: Mint Agent NFT (or use existing) ==========
    print("\n" + "-" * 40)
    print("STEP 1: Checking/Minting Agent NFT")
    print("-" * 40)
    
    # Check if token 1 already exists
    token_id = 1
    try:
        existing_owner = contract.functions.ownerOf(token_id).call()
        print(f"Token {token_id} already exists, owned by: {existing_owner}")
        print("Skipping mint, using existing token")
    except Exception as e:
        # Token doesn't exist, mint it
        print(f"Token {token_id} doesn't exist, minting...")
        token_uri = "ipfs://QmTest123/metadata.json"  # Placeholder URI
        
        mint_tx = contract.functions.mintAgent(
            deployer.address,  # to (initial owner)
            token_uri,
            executor.address,  # initial executor
            executor_permissions
        ).build_transaction({
            'from': deployer.address,
        })
        
        print(f"Minting to: {deployer.address}")
        print(f"Token URI: {token_uri}")
        print(f"Initial executor: {executor.address}")
        
        receipt = send_transaction(w3, deployer, mint_tx)
        
        if receipt['status'] != 1:
            print("ERROR: Mint transaction failed")
            sys.exit(1)
        
        print(f"Mint successful! TX: {receipt['transactionHash'].hex()}")
        print(f"Gas used: {receipt['gasUsed']}")
    
    print(f"Token ID: {token_id}")
    
    # Get TBA address
    tba_address = contract.functions.getAgentTBA(token_id).call()
    print(f"TBA Address: {tba_address}")
    
    # ========== STEP 2: Create Mock Letta State ==========
    print("\n" + "-" * 40)
    print("STEP 2: Creating Mock Letta State")
    print("-" * 40)
    
    state = create_mock_letta_state()
    print(f"Agent ID: {state['agent_id']}")
    print(f"Agent Name: {state['agent_name']}")
    print(f"Memory blocks: {list(state['memory_blocks'].keys())}")
    print(f"Archival memories: {state['archival_memory_count']}")
    print(f"Messages: {state['message_count']}")
    
    # ========== STEP 3: Hash the State ==========
    print("\n" + "-" * 40)
    print("STEP 3: Hashing State (keccak256)")
    print("-" * 40)
    
    state_hash = hash_state(state)
    print(f"State hash: {state_hash.hex()}")
    
    # In production, the state would be encrypted and uploaded to IPFS/Arweave
    state_uri = "ipfs://QmStateHash123/encrypted_state.json"
    print(f"State URI: {state_uri}")
    
    # ========== STEP 4: Anchor State On-Chain ==========
    print("\n" + "-" * 40)
    print("STEP 4: Anchoring State On-Chain")
    print("-" * 40)
    
    # Fund executor if needed (before building transaction)
    executor_balance = w3.eth.get_balance(executor.address)
    print(f"Executor balance: {w3.from_wei(executor_balance, 'ether'):.6f} ETH")
    if executor_balance < w3.to_wei(0.0001, 'ether'):
        print("Funding executor wallet...")
        fund_tx = {
            'to': executor.address,
            'value': w3.to_wei(0.0002, 'ether'),  # Fund with more to be safe
            'from': deployer.address,
        }
        send_transaction(w3, deployer, fund_tx)
        print(f"Funded executor with 0.0002 ETH")
        executor_balance = w3.eth.get_balance(executor.address)
        print(f"New executor balance: {w3.from_wei(executor_balance, 'ether'):.6f} ETH")
    
    # Now build and send the anchor transaction
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
    
    # ========== STEP 5: Verify State Anchor ==========
    print("\n" + "-" * 40)
    print("STEP 5: Verifying State Anchor")
    print("-" * 40)
    
    anchor = contract.functions.getStateAnchor(token_id).call()
    stored_hash, stored_uri, timestamp = anchor
    
    print(f"Stored hash: {stored_hash.hex()}")
    print(f"Stored URI: {stored_uri}")
    print(f"Timestamp: {timestamp}")
    
    # Verify hash matches
    if stored_hash == state_hash:
        print("\n[SUCCESS] State hash matches!")
    else:
        print("\n[FAILURE] State hash mismatch!")
        sys.exit(1)
    
    # ========== Summary ==========
    print("\n" + "=" * 60)
    print("INTEGRATION TEST COMPLETE")
    print("=" * 60)
    print(f"""
Results:
  - Token ID: {token_id}
  - TBA Address: {tba_address}
  - State Hash: {state_hash.hex()[:20]}...
  - State URI: {state_uri}
  - Anchor Timestamp: {timestamp}

The integration test validates:
  1. Agent NFT can be minted with executor permissions
  2. Letta state can be serialized and hashed deterministically  
  3. State hash can be anchored on-chain via executor
  4. Anchored state can be retrieved and verified

Next steps:
  - Integrate with real Letta agent state export
  - Upload encrypted state to IPFS/Arweave
  - Implement state verification in Letta tools
""")


if __name__ == "__main__":
    main()
