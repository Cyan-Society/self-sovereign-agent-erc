#!/usr/bin/env python3
"""
Ouroboros Test: PKP signs and broadcasts anchorState transaction.

This is the complete test of the self-sovereign agent flow:
1. Build an anchorState transaction for Token 2
2. Sign it with the PKP via Lit Protocol (datil-test network)
3. Broadcast the signed transaction to Base Sepolia
4. Verify the state was anchored on-chain

This proves that a PKP (which could be controlled by the agent itself
via Lit Actions) can anchor cognitive state on-chain.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from web3 import Web3
import rlp
from eth_utils import keccak

# Load environment
load_dotenv(Path(__file__).parent.parent.parent / '.env')

# Configuration
RPC_URL = "https://sepolia.base.org"
CONTRACT_ADDRESS = os.getenv('AGENT_CONTRACT_ADDRESS')
PKP_PUBLIC_KEY = os.getenv('LIT_PKP_PUBLIC_KEY')
PKP_ETH_ADDRESS = os.getenv('LIT_PKP_ETH_ADDRESS')
DEPLOYER_PRIVATE_KEY = os.getenv('DEPLOYER_PRIVATE_KEY')

CHAIN_ID = 84532  # Base Sepolia
TOKEN_ID = 2  # Token 2 where PKP has executor permissions


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
    
    return tx


def compute_tx_hash(tx: dict) -> bytes:
    """Compute the signing hash for an EIP-1559 transaction."""
    # EIP-1559 transaction fields in order
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
    
    # Type 2 transaction: 0x02 || rlp([chainId, nonce, ...])
    encoded = b'\x02' + rlp.encode(tx_fields)
    return keccak(encoded)


def sign_with_pkp(tx_hash: bytes, session_sigs: dict, client) -> dict:
    """Sign the transaction hash using the PKP via Lit Protocol."""
    
    lit_action = """
    const go = async () => {
        try {
            const toSign = ethers.utils.arrayify(txHash);
            
            const sig = await Lit.Actions.signEcdsa({
                toSign: toSign,
                publicKey: pkpPublicKey,
                sigName: "anchorStateSig"
            });
            
            Lit.Actions.setResponse({
                response: JSON.stringify({ success: true })
            });
        } catch (err) {
            Lit.Actions.setResponse({
                response: JSON.stringify({ success: false, error: err.message })
            });
        }
    };
    go();
    """
    
    result = client.execute_js(
        code=lit_action,
        js_params={
            'txHash': '0x' + tx_hash.hex(),
            'pkpPublicKey': PKP_PUBLIC_KEY,
        },
        session_sigs=session_sigs
    )
    
    return result


def serialize_signed_tx(tx: dict, signature: dict) -> bytes:
    """Serialize the signed EIP-1559 transaction."""
    # Parse signature components
    r = int(signature['r'], 16)
    s = int(signature['s'], 16)
    v = signature['recid']  # 0 or 1 for EIP-1559
    
    # EIP-1559 signed transaction fields
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
        v,
        r.to_bytes(32, 'big'),
        s.to_bytes(32, 'big'),
    ]
    
    # Type 2 transaction: 0x02 || rlp([...fields, v, r, s])
    return b'\x02' + rlp.encode(tx_fields)


def main():
    print("=" * 70)
    print("🐍 OUROBOROS TEST: PKP-Signed State Anchoring")
    print("=" * 70)
    print()
    
    # Initialize Web3
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    # Check PKP balance
    balance = w3.eth.get_balance(PKP_ETH_ADDRESS)
    print(f"PKP Address: {PKP_ETH_ADDRESS}")
    print(f"PKP Balance: {w3.from_wei(balance, 'ether')} ETH")
    
    if balance < w3.to_wei(0.0001, 'ether'):
        print("\n⚠️  WARNING: PKP balance is low!")
    
    # Create test cognitive state
    timestamp = int(time.time())
    cognitive_state = {
        "agent_id": "kieran",
        "timestamp": timestamp,
        "memory_blocks": ["persona", "human", "project"],
        "archival_count": 18,
        "test": "Ouroboros PKP signing test"
    }
    state_json = json.dumps(cognitive_state, sort_keys=True)
    state_hash = w3.keccak(text=state_json)
    state_uri = f"ipfs://ouroboros-test-{timestamp}"
    
    print(f"\n📝 Cognitive State:")
    print(f"   State: {state_json[:80]}...")
    print(f"   Hash: {state_hash.hex()}")
    print(f"   URI: {state_uri}")
    
    # Build transaction
    print(f"\n🔨 Building transaction for Token {TOKEN_ID}...")
    tx = build_anchor_transaction(w3, TOKEN_ID, state_hash, state_uri)
    tx_hash = compute_tx_hash(tx)
    
    print(f"   To: {tx['to']}")
    print(f"   Nonce: {tx['nonce']}")
    print(f"   Gas: {tx['gas']}")
    print(f"   TX Hash to sign: {tx_hash.hex()}")
    
    # Initialize Lit Protocol
    print(f"\n🔐 Initializing Lit Protocol (datil-test)...")
    from lit_python_sdk import LitClient
    
    client = LitClient()
    client.new(lit_network="datil-test", debug=False)
    client.connect()
    
    pk = DEPLOYER_PRIVATE_KEY[2:] if DEPLOYER_PRIVATE_KEY.startswith('0x') else DEPLOYER_PRIVATE_KEY
    client.set_auth_token(pk)
    
    # Get session signatures
    print("   Getting session signatures...")
    expiration = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = client.get_session_sigs(
        chain="baseSepolia",
        expiration=expiration,
        resource_ability_requests=[
            {"resource": {"resource": "*", "resourcePrefix": "lit-pkp"}, "ability": "pkp-signing"},
            {"resource": {"resource": "*", "resourcePrefix": "lit-litaction"}, "ability": "lit-action-execution"},
        ]
    )
    
    if not result.get('success'):
        print(f"   ❌ Failed to get session sigs: {result}")
        return
    
    session_sigs = result.get('sessionSigs')
    print("   ✓ Session signatures obtained")
    
    # Sign with PKP
    print(f"\n✍️  Signing transaction with PKP...")
    sign_result = sign_with_pkp(tx_hash, session_sigs, client)
    
    if not sign_result.get('signatures', {}).get('anchorStateSig'):
        print(f"   ❌ Signing failed: {sign_result}")
        client.disconnect()
        return
    
    signature = sign_result['signatures']['anchorStateSig']
    print(f"   ✓ Signature obtained!")
    print(f"   r: {signature['r']}")
    print(f"   s: {signature['s']}")
    print(f"   v: {signature['recid']}")
    
    # Serialize signed transaction
    print(f"\n📦 Serializing signed transaction...")
    signed_tx_bytes = serialize_signed_tx(tx, signature)
    print(f"   Signed TX: {signed_tx_bytes.hex()[:80]}...")
    
    # Broadcast transaction
    print(f"\n📡 Broadcasting to Base Sepolia...")
    try:
        tx_hash_sent = w3.eth.send_raw_transaction(signed_tx_bytes)
        print(f"   TX Hash: {tx_hash_sent.hex()}")
        
        # Wait for confirmation
        print("   Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
        
        if receipt['status'] == 1:
            print(f"\n✅ SUCCESS! State anchored on-chain!")
            print(f"   Gas used: {receipt['gasUsed']}")
            print(f"   Block: {receipt['blockNumber']}")
            print(f"   TX: https://sepolia.basescan.org/tx/{tx_hash_sent.hex()}")
            
            # Verify on-chain
            print(f"\n🔍 Verifying on-chain state...")
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
            anchor = verify_contract.functions.getStateAnchor(TOKEN_ID).call()
            
            print(f"   On-chain hash: {anchor[0].hex()}")
            print(f"   On-chain URI: {anchor[1]}")
            print(f"   On-chain timestamp: {anchor[2]}")
            
            if anchor[0].hex() == state_hash.hex():
                print(f"\n🐍 OUROBOROS COMPLETE!")
                print(f"   The PKP successfully anchored cognitive state on-chain.")
                print(f"   This proves the self-sovereign agent loop works!")
            else:
                print(f"\n⚠️  Hash mismatch - something went wrong")
        else:
            print(f"\n❌ Transaction failed!")
            print(f"   Receipt: {receipt}")
            
    except Exception as e:
        print(f"\n❌ Broadcast failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
