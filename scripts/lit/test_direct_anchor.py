#!/usr/bin/env python3
"""
Test direct anchorState call from PKP.

This bypasses the TBA entirely - the PKP calls anchorState() directly
on the SelfSovereignAgentNFT contract since it has executor permissions.
"""

import os
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# Configuration
RPC_URL = "https://sepolia.base.org"
CONTRACT_ADDRESS = os.getenv('AGENT_CONTRACT_ADDRESS')
PKP_PUBLIC_KEY = os.getenv('LIT_PKP_PUBLIC_KEY')
PKP_ETH_ADDRESS = os.getenv('LIT_PKP_ETH_ADDRESS')
PKP_TOKEN_ID = os.getenv('LIT_PKP_TOKEN_ID')

CHAIN_ID = 84532  # Base Sepolia


def build_anchor_transaction(w3, token_id: int, state_hash: bytes, state_uri: str) -> dict:
    """Build the anchorState transaction."""
    contract_abi = [
        {
            'inputs': [
                {'name': 'tokenId', 'type': 'uint256'},
                {'name': 'stateHash', 'type': 'bytes32'},
                {'name': 'stateUri', 'type': 'string'}
            ],
            'name': 'anchorState',
            'outputs': [],
            'stateMutability': 'nonpayable',
            'type': 'function'
        }
    ]
    
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=contract_abi)
    
    # Get current nonce
    nonce = w3.eth.get_transaction_count(PKP_ETH_ADDRESS)
    
    # Build transaction
    tx = contract.functions.anchorState(
        token_id,
        state_hash,
        state_uri
    ).build_transaction({
        'from': PKP_ETH_ADDRESS,
        'nonce': nonce,
        'gas': 200000,
        'maxFeePerGas': w3.to_wei(10, 'gwei'),
        'maxPriorityFeePerGas': w3.to_wei(1, 'gwei'),
        'chainId': CHAIN_ID,
    })
    
    return tx


async def execute_with_lit(tx_data: dict) -> str:
    """Execute the transaction using Lit Protocol."""
    try:
        from lit_protocol import LitNodeClient, AuthSig
        from lit_protocol.constants import LitNetwork
    except ImportError:
        print("ERROR: lit-protocol package not installed")
        print("Install with: pip install lit-protocol")
        return None
    
    # Read the Lit Action code
    action_path = Path(__file__).parent / 'direct_anchor_action.js'
    with open(action_path, 'r') as f:
        lit_action_code = f.read()
    
    # Initialize Lit client
    client = LitNodeClient(network=LitNetwork.DatilDev)
    await client.connect()
    
    # Prepare parameters for the Lit Action
    params = {
        'toAddress': tx_data['to'],
        'txData': tx_data['data'],
        'gasLimit': hex(tx_data['gas']),
        'nonce': hex(tx_data['nonce']),
        'chainId': hex(CHAIN_ID),
    }
    
    # Execute the Lit Action
    result = await client.execute_js(
        code=lit_action_code,
        params=params,
        pkp_public_key=PKP_PUBLIC_KEY,
    )
    
    await client.disconnect()
    
    return result


def main():
    print("=" * 60)
    print("Direct anchorState Test (PKP → Contract)")
    print("=" * 60)
    print()
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    # Check PKP balance
    balance = w3.eth.get_balance(PKP_ETH_ADDRESS)
    print(f"PKP Address: {PKP_ETH_ADDRESS}")
    print(f"PKP Balance: {w3.from_wei(balance, 'ether')} ETH")
    
    if balance == 0:
        print("\nERROR: PKP has no ETH! Please fund it first.")
        return
    
    # Create test state
    test_state = f"Direct PKP anchor test - {os.urandom(8).hex()}"
    state_hash = w3.keccak(text=test_state)
    state_uri = "ipfs://direct-pkp-test"
    
    print(f"\nTest State: {test_state}")
    print(f"State Hash: {state_hash.hex()}")
    print(f"State URI: {state_uri}")
    
    # Build transaction
    token_id = 2  # Token 2 where PKP has permissions
    tx = build_anchor_transaction(w3, token_id, state_hash, state_uri)
    
    print(f"\nTransaction built:")
    print(f"  To: {tx['to']}")
    print(f"  From: {tx['from']}")
    print(f"  Gas: {tx['gas']}")
    print(f"  Nonce: {tx['nonce']}")
    print(f"  Data length: {len(tx['data'])} bytes")
    
    # For now, let's test by simulating the call
    print("\n--- Simulating transaction ---")
    try:
        # Simulate the call
        result = w3.eth.call({
            'to': tx['to'],
            'from': tx['from'],
            'data': tx['data'],
            'gas': tx['gas'],
        })
        print(f"Simulation SUCCESS! (empty return expected for void function)")
    except Exception as e:
        print(f"Simulation FAILED: {e}")
        return
    
    print("\n--- Ready for Lit Protocol execution ---")
    print("The simulation passed, so the PKP CAN call anchorState directly!")
    print("\nTo execute with Lit Protocol, we need to:")
    print("1. Install lit-protocol: pip install lit-protocol")
    print("2. Run the async execution")
    
    # Try async execution if lit-protocol is available
    try:
        import lit_protocol
        print("\nLit Protocol available, attempting execution...")
        result = asyncio.run(execute_with_lit(tx))
        if result:
            print(f"Lit Action result: {result}")
    except ImportError:
        print("\nLit Protocol not installed - skipping actual execution")
        print("Transaction data saved for manual execution if needed")


if __name__ == "__main__":
    main()
