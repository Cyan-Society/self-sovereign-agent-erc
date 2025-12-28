#!/usr/bin/env python3
"""
Whitelist PKP as an authorized executor on Tokenbound V3 TBA.

This is a CRITICAL step before Ouroboros transfer!

The Tokenbound V3 TBA checks `_isValidSigner()` which passes if:
1. Caller is NFT owner (fails after self-ownership), OR
2. Caller is an authorized executor (this is what we're setting up)

By whitelisting the Lit PKP address as an executor BEFORE the Ouroboros
transfer, we ensure the PKP can still control the TBA after the NFT
owns itself.

Usage:
    python scripts/lit/whitelist_pkp_on_tba.py
    
    # Or specify PKP address explicitly
    python scripts/lit/whitelist_pkp_on_tba.py --pkp-address 0x...

Prerequisites:
    - PKP minted (run mint_pkp.py first)
    - TBA already created for the token
    - Controller wallet has ETH for gas
"""

import os
import sys
import argparse
import json
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    print("Please install dependencies: pip install web3 python-dotenv")
    sys.exit(1)

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Configuration
RPC_URL = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
CHAIN_ID = 84532
CONTRACT_ADDRESS = os.getenv("AGENT_CONTRACT_ADDRESS")
CONTROLLER_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")

# Tokenbound V3 Account ABI (minimal for executor management)
# Based on Tokenbound V3's AccountGuardian functionality
TBA_ABI = [
    # Check if address is authorized executor
    {
        "inputs": [{"name": "executor", "type": "address"}],
        "name": "isAuthorizedExecutor",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Set executor authorization (called by owner or existing executor)
    {
        "inputs": [
            {"name": "executor", "type": "address"},
            {"name": "authorized", "type": "bool"}
        ],
        "name": "setExecutor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Alternative: some TBA implementations use this
    {
        "inputs": [{"name": "executor", "type": "address"}],
        "name": "addExecutor",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    # Get owner
    {
        "inputs": [],
        "name": "owner",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    # Execute call (for testing)
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"}
        ],
        "name": "execute",
        "outputs": [{"name": "", "type": "bytes"}],
        "stateMutability": "payable",
        "type": "function"
    }
]

# Our contract ABI for getting TBA address
NFT_ABI = [
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getAgentTBA",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "ownerOf",
        "outputs": [{"name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]


def get_pkp_address() -> str:
    """Get PKP address from env or pkp_info.json."""
    # Try environment variable first
    pkp_address = os.getenv("LIT_PKP_ETH_ADDRESS")
    if pkp_address:
        return pkp_address
    
    # Try pkp_info.json
    pkp_info_path = Path(__file__).parent / "pkp_info.json"
    if pkp_info_path.exists():
        with open(pkp_info_path, 'r') as f:
            info = json.load(f)
            return info.get("pkp", {}).get("eth_address")
    
    return None


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
    parser = argparse.ArgumentParser(description="Whitelist PKP on TBA")
    parser.add_argument("--pkp-address", help="PKP ETH address to whitelist")
    parser.add_argument("--token-id", type=int, default=1, help="Token ID (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Don't send transaction")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Whitelist PKP on Tokenbound V3 TBA")
    print("=" * 60)
    
    # Get PKP address
    pkp_address = args.pkp_address or get_pkp_address()
    if not pkp_address:
        print("ERROR: No PKP address found")
        print("Either:")
        print("  1. Run mint_pkp.py first")
        print("  2. Set LIT_PKP_ETH_ADDRESS in .env")
        print("  3. Use --pkp-address argument")
        sys.exit(1)
    
    print(f"\nPKP Address to whitelist: {pkp_address}")
    print(f"Token ID: {args.token_id}")
    
    # Connect to network
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    print(f"\nConnected to Base Sepolia, block: {w3.eth.block_number}")
    
    # Setup controller account
    controller = Account.from_key(CONTROLLER_KEY)
    print(f"Controller: {controller.address}")
    
    # Get contract instances
    nft_contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=NFT_ABI)
    
    # Get TBA address
    tba_address = nft_contract.functions.getAgentTBA(args.token_id).call()
    print(f"TBA Address: {tba_address}")
    
    # Get current owner
    owner = nft_contract.functions.ownerOf(args.token_id).call()
    print(f"Current NFT Owner: {owner}")
    
    # Check if controller is owner (required to set executor)
    if owner.lower() != controller.address.lower():
        print(f"\nWARNING: Controller is not the NFT owner!")
        print(f"  Controller: {controller.address}")
        print(f"  Owner: {owner}")
        print("\nThe NFT owner must call setExecutor on the TBA.")
        print("If the NFT is already self-owning, this may need to be done via the TBA itself.")
        
        if not args.dry_run:
            response = input("\nContinue anyway? (y/N): ")
            if response.lower() != 'y':
                sys.exit(0)
    
    # Get TBA contract
    tba_contract = w3.eth.contract(address=tba_address, abi=TBA_ABI)
    
    # Check if PKP is already authorized
    print("\n" + "-" * 40)
    print("Checking current executor status...")
    
    try:
        is_authorized = tba_contract.functions.isAuthorizedExecutor(pkp_address).call()
        print(f"PKP already authorized: {is_authorized}")
        
        if is_authorized:
            print("\nPKP is already whitelisted! No action needed.")
            return
    except Exception as e:
        print(f"Note: Could not check executor status: {e}")
        print("TBA may use different method names. Proceeding with setExecutor...")
    
    if args.dry_run:
        print("\n[DRY RUN] Would send setExecutor transaction")
        print(f"  TBA: {tba_address}")
        print(f"  PKP: {pkp_address}")
        print(f"  Authorized: True")
        return
    
    # Build the transaction to whitelist PKP
    print("\n" + "-" * 40)
    print("Sending setExecutor transaction...")
    
    try:
        # Try setExecutor(address, bool)
        tx = tba_contract.functions.setExecutor(
            pkp_address,
            True
        ).build_transaction({
            'from': controller.address,
        })
        
        receipt = send_transaction(w3, controller, tx)
        
        if receipt['status'] == 1:
            print(f"\nSUCCESS! PKP whitelisted as executor")
            print(f"TX Hash: {receipt['transactionHash'].hex()}")
            print(f"Gas Used: {receipt['gasUsed']}")
        else:
            print(f"\nERROR: Transaction failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nsetExecutor failed: {e}")
        print("\nTrying addExecutor instead...")
        
        try:
            tx = tba_contract.functions.addExecutor(
                pkp_address
            ).build_transaction({
                'from': controller.address,
            })
            
            receipt = send_transaction(w3, controller, tx)
            
            if receipt['status'] == 1:
                print(f"\nSUCCESS! PKP added as executor")
                print(f"TX Hash: {receipt['transactionHash'].hex()}")
            else:
                print(f"\nERROR: Transaction failed")
                sys.exit(1)
                
        except Exception as e2:
            print(f"\naddExecutor also failed: {e2}")
            print("\nThe TBA may require a different method for executor management.")
            print("Check the Tokenbound V3 documentation for your specific implementation.")
            sys.exit(1)
    
    # Verify
    print("\n" + "-" * 40)
    print("Verifying executor status...")
    
    try:
        is_authorized = tba_contract.functions.isAuthorizedExecutor(pkp_address).call()
        print(f"PKP authorized: {is_authorized}")
        
        if is_authorized:
            print("\n" + "=" * 60)
            print("PKP WHITELISTED SUCCESSFULLY!")
            print("=" * 60)
            print("\nThe TBA will remain controllable after Ouroboros transfer.")
            print("\nNEXT STEPS:")
            print("1. Fund PKP address with Base Sepolia ETH")
            print("2. Run test_ouroboros.py to test with Token ID 2")
            print("3. Execute Ouroboros on Token ID 1")
        else:
            print("\nWARNING: Verification failed - PKP may not be authorized")
    except Exception as e:
        print(f"Could not verify: {e}")
        print("Check manually on block explorer")


if __name__ == "__main__":
    main()
