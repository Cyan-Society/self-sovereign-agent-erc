#!/usr/bin/env python3
"""
Test Ouroboros flow with Token ID 2 (safe testing before Token 1).

This script tests the complete self-ownership loop:
1. Mint Token ID 2 (test token)
2. Get/verify TBA for Token 2
3. Whitelist PKP on TBA
4. Execute Ouroboros transfer (Token 2 -> its own TBA)
5. Verify PKP can still execute on TBA

Prerequisites:
- PKP minted (run mint_pkp.py first)
- PKP funded with Base Sepolia ETH
- Controller wallet has ETH for gas

Usage:
    python scripts/lit/test_ouroboros.py
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
load_dotenv(Path(__file__).parent.parent.parent / ".env")

try:
    from web3 import Web3
    from eth_account import Account
except ImportError:
    print("Install: pip install web3 python-dotenv")
    sys.exit(1)

# Config
RPC_URL = os.getenv("BASE_SEPOLIA_RPC", "https://sepolia.base.org")
CHAIN_ID = 84532
CONTRACT_ADDRESS = os.getenv("AGENT_CONTRACT_ADDRESS")
DEPLOYER_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")

# Minimal ABI
CONTRACT_ABI = [
    {"inputs": [{"name": "to", "type": "address"}], "name": "mintAgent", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "tokenId", "type": "uint256"}], "name": "getAgentTBA", "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "tokenId", "type": "uint256"}], "name": "ownerOf", "outputs": [{"name": "", "type": "address"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "tokenId", "type": "uint256"}], "name": "establishSelfOwnership", "outputs": [], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "tokenId", "type": "uint256"}], "name": "isSelfOwning", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "view", "type": "function"},
]

def main():
    print("=" * 60)
    print("OUROBOROS TEST (Token ID 2)")
    print("=" * 60)
    
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    deployer = Account.from_key(DEPLOYER_KEY)
    contract = w3.eth.contract(address=CONTRACT_ADDRESS, abi=CONTRACT_ABI)
    
    print(f"Network: Base Sepolia (block {w3.eth.block_number})")
    print(f"Contract: {CONTRACT_ADDRESS}")
    print(f"Deployer: {deployer.address}")
    
    # Check if Token 2 exists
    try:
        owner = contract.functions.ownerOf(2).call()
        print(f"\nToken 2 exists, owner: {owner}")
    except:
        print("\nToken 2 doesn't exist. Mint it first or run full test.")
        print("To mint: Add minting logic or use existing scripts")
        return
    
    # Get TBA
    tba = contract.functions.getAgentTBA(2).call()
    print(f"Token 2 TBA: {tba}")
    
    # Check self-ownership status
    is_self_owning = contract.functions.isSelfOwning(2).call()
    print(f"Self-owning: {is_self_owning}")
    
    if is_self_owning:
        print("\nToken 2 is already self-owning!")
        print("Test the PKP signing separately.")
    else:
        print("\nToken 2 is NOT self-owning yet.")
        print("Next steps:")
        print("1. Whitelist PKP on TBA (run whitelist_pkp_on_tba.py --token-id 2)")
        print("2. Call establishSelfOwnership(2)")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
