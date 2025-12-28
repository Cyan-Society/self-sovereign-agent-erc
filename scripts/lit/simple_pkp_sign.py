#!/usr/bin/env python3
"""
Simple PKP signing test using Lit Protocol execute_js.

This approach uses a Lit Action to sign the transaction directly,
which is the recommended pattern for PKP signing.
"""

import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# Configuration
RPC_URL = "https://sepolia.base.org"
CONTRACT_ADDRESS = os.getenv('AGENT_CONTRACT_ADDRESS')
PKP_PUBLIC_KEY = os.getenv('LIT_PKP_PUBLIC_KEY')
PKP_ETH_ADDRESS = os.getenv('LIT_PKP_ETH_ADDRESS')
PKP_TOKEN_ID = os.getenv('LIT_PKP_TOKEN_ID')
DEPLOYER_PRIVATE_KEY = os.getenv('DEPLOYER_PRIVATE_KEY')

CHAIN_ID = 84532  # Base Sepolia

# Lit Action code for signing a transaction
LIT_ACTION_CODE = """
const go = async () => {
    // Get the transaction hash to sign
    const toSign = ethers.utils.arrayify(txHash);
    
    // Sign with the PKP
    const sigShare = await Lit.Actions.signEcdsa({
        toSign: toSign,
        publicKey: pkpPublicKey,
        sigName: "sig1"
    });
    
    // Return the signature
    Lit.Actions.setResponse({
        response: JSON.stringify({
            success: true,
            signature: sigShare
        })
    });
};

go();
"""


def main():
    print("=" * 60)
    print("Simple PKP Signing Test")
    print("=" * 60)
    print()
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    # Check PKP balance
    balance = w3.eth.get_balance(PKP_ETH_ADDRESS)
    print(f"PKP Address: {PKP_ETH_ADDRESS}")
    print(f"PKP Public Key: {PKP_PUBLIC_KEY[:20]}...")
    print(f"PKP Balance: {w3.from_wei(balance, 'ether')} ETH")
    
    # Create test state
    test_state = f"Ouroboros test - {int(time.time())}"
    state_hash = w3.keccak(text=test_state)
    state_uri = f"ipfs://ouroboros-test-{int(time.time())}"
    
    print(f"\nTest State: {test_state}")
    print(f"State Hash: {state_hash.hex()}")
    
    # Build transaction
    token_id = 2
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
    nonce = w3.eth.get_transaction_count(PKP_ETH_ADDRESS)
    
    # Get current gas prices
    base_fee = w3.eth.get_block('latest')['baseFeePerGas']
    max_priority_fee = w3.to_wei(1, 'gwei')
    max_fee = base_fee * 2 + max_priority_fee
    
    tx_data = contract.encode_abi('anchorState', [token_id, state_hash, state_uri])
    
    tx = {
        'to': CONTRACT_ADDRESS,
        'value': 0,
        'data': tx_data,
        'gas': 200000,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': max_priority_fee,
        'nonce': nonce,
        'chainId': CHAIN_ID,
        'type': 2,
    }
    
    print(f"\nTransaction:")
    print(f"  To: {tx['to']}")
    print(f"  Nonce: {tx['nonce']}")
    print(f"  Gas: {tx['gas']}")
    
    # Compute transaction hash for signing
    import rlp
    from eth_utils import keccak
    
    tx_fields = [
        tx['chainId'],
        tx['nonce'],
        tx['maxPriorityFeePerGas'],
        tx['maxFeePerGas'],
        tx['gas'],
        bytes.fromhex(tx['to'][2:]),
        tx['value'],
        bytes.fromhex(tx['data'][2:]),
        [],  # access list
    ]
    
    encoded = b'\x02' + rlp.encode(tx_fields)
    tx_hash = keccak(encoded)
    
    print(f"\nTransaction hash: {tx_hash.hex()}")
    
    # Try Lit Protocol
    print("\n--- Attempting Lit Protocol signing ---")
    try:
        from lit_python_sdk import LitClient
        
        client = LitClient()
        
        # Initialize
        result = client.new(lit_network="datil-dev", debug=False)
        if not result.get('success'):
            raise Exception(f"Init failed: {result}")
        
        # Connect
        result = client.connect()
        if not result.get('success'):
            raise Exception(f"Connect failed: {result}")
        
        print("Connected to Lit network!")
        
        # Execute the Lit Action
        # The Lit Action needs session signatures to authorize the PKP signing
        # For testing, let's first verify the PKP exists and is accessible
        
        # Try a simple execute_js with minimal params
        simple_action = """
        const go = async () => {
            // Just return some info
            Lit.Actions.setResponse({
                response: JSON.stringify({
                    success: true,
                    message: "Lit Action executed!",
                    pkpPublicKey: pkpPublicKey
                })
            });
        };
        go();
        """
        
        print("\nTesting simple Lit Action...")
        result = client.execute_js(
            code=simple_action,
            js_params={
                'pkpPublicKey': PKP_PUBLIC_KEY,
            }
        )
        print(f"Result: {result}")
        
        client.disconnect()
        
    except Exception as e:
        print(f"Lit Protocol error: {e}")
        import traceback
        traceback.print_exc()
    
    # Fallback test with deployer
    print("\n" + "=" * 60)
    print("FALLBACK: Testing contract with deployer wallet")
    print("=" * 60)
    
    deployer = Account.from_key(DEPLOYER_PRIVATE_KEY)
    deployer_balance = w3.eth.get_balance(deployer.address)
    
    print(f"\nDeployer: {deployer.address}")
    print(f"Balance: {w3.from_wei(deployer_balance, 'ether')} ETH")
    
    if deployer_balance < w3.to_wei(0.0001, 'ether'):
        print("ERROR: Deployer has insufficient balance")
        return
    
    # Build transaction for Token 1 (owned by deployer)
    token_1_state = f"Token 1 anchor test - {int(time.time())}"
    token_1_hash = w3.keccak(text=token_1_state)
    token_1_uri = f"ipfs://token1-test-{int(time.time())}"
    
    test_tx = {
        'to': CONTRACT_ADDRESS,
        'value': 0,
        'data': contract.encode_abi('anchorState', [1, token_1_hash, token_1_uri]),
        'gas': 200000,
        'maxFeePerGas': max_fee,
        'maxPriorityFeePerGas': max_priority_fee,
        'nonce': w3.eth.get_transaction_count(deployer.address),
        'chainId': CHAIN_ID,
        'type': 2,
    }
    
    print(f"\nAnchoring state for Token 1...")
    print(f"State: {token_1_state}")
    print(f"Hash: {token_1_hash.hex()}")
    
    # Sign and send
    signed_tx = deployer.sign_transaction(test_tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Transaction sent: {tx_hash.hex()}")
    
    # Wait for receipt
    print("Waiting for confirmation...")
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    
    if receipt['status'] == 1:
        print(f"\n✅ SUCCESS!")
        print(f"   Gas used: {receipt['gasUsed']}")
        print(f"   Block: {receipt['blockNumber']}")
        print(f"   Tx: https://sepolia.basescan.org/tx/{tx_hash.hex()}")
        
        # Verify the state was anchored
        verify_abi = [
            {
                'inputs': [{'name': 'tokenId', 'type': 'uint256'}],
                'name': 'getStateAnchor',
                'outputs': [
                    {'name': 'stateHash', 'type': 'bytes32'},
                    {'name': 'stateUri', 'type': 'string'},
                    {'name': 'timestamp', 'type': 'uint256'}
                ],
                'stateMutability': 'view',
                'type': 'function'
            }
        ]
        verify_contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=verify_abi)
        anchor = verify_contract.functions.getStateAnchor(1).call()
        
        print(f"\n   Verified on-chain:")
        print(f"   - Hash: {anchor[0].hex()}")
        print(f"   - URI: {anchor[1]}")
        print(f"   - Timestamp: {anchor[2]}")
    else:
        print(f"\n❌ FAILED!")
        print(f"   Receipt: {receipt}")


if __name__ == "__main__":
    main()
