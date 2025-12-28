#!/usr/bin/env python3
"""
Mint a Programmable Key Pair (PKP) on Lit Protocol's Datil-Test network.

This script:
1. Connects to Lit Protocol's Datil-Test network
2. Generates an AuthSig using the controller wallet
3. Mints a new PKP with EthWallet auth method
4. Outputs the PKP details for use in subsequent scripts

Prerequisites:
- Node.js 19+ installed
- pip install lit-python-sdk
- Controller wallet funded with tstLPX tokens

Usage:
    python scripts/lit/mint_pkp.py
    
Environment:
    LIT_CONTROLLER_PRIVATE_KEY or DEPLOYER_PRIVATE_KEY in .env
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# Try to import lit_python_sdk
try:
    from lit_python_sdk import connect
    from eth_account import Account
except ImportError:
    print("ERROR: lit-python-sdk not installed")
    print("Install with: pip install lit-python-sdk")
    print("\nNote: This requires Node.js 19+ to be installed")
    sys.exit(1)


# Configuration
LIT_NETWORK = os.getenv("LIT_NETWORK", "datil-test")
CONTROLLER_PRIVATE_KEY = os.getenv("LIT_CONTROLLER_PRIVATE_KEY") or os.getenv("DEPLOYER_PRIVATE_KEY")

if not CONTROLLER_PRIVATE_KEY:
    print("ERROR: No controller private key found")
    print("Set LIT_CONTROLLER_PRIVATE_KEY or DEPLOYER_PRIVATE_KEY in .env")
    sys.exit(1)


def mint_pkp():
    """Mint a new PKP on Lit Protocol."""
    
    print("=" * 60)
    print("Lit Protocol PKP Minting")
    print(f"Network: {LIT_NETWORK}")
    print("=" * 60)
    
    # Initialize the Lit client
    print("\n[1/4] Connecting to Lit Network...")
    client = connect()
    client.set_auth_token(CONTROLLER_PRIVATE_KEY)
    
    try:
        client.new(lit_network=LIT_NETWORK, debug=True)
        result = client.connect()  # Synchronous call, returns dict
        print(f"Connection result: {result}")
        
        # Get wallet address from private key directly (SDK's get_property is unreliable)
        account = Account.from_key(CONTROLLER_PRIVATE_KEY)
        wallet_address = account.address
        print(f"Connected! Controller wallet: {wallet_address}")
    except Exception as e:
        print(f"ERROR: Failed to connect to Lit Network: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure Node.js 19+ is installed")
        print("2. Check that controller wallet has tstLPX tokens")
        print("3. Try: node --version")
        sys.exit(1)
    
    # Create SIWE message for authentication
    print("\n[2/4] Generating authentication signature...")
    expiration = (datetime.now(timezone.utc) + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    try:
        siwe_result = client.create_siwe_message(
            uri="http://localhost:3092",
            expiration=expiration,
            resources=[{
                "resource": {
                    "resource": "*",
                    "resourcePrefix": "lit-litaction",
                },
                "ability": "lit-action-execution",
            }],
            wallet_address=wallet_address
        )
        print(f"SIWE message created")
        
        # Generate the signature
        auth_sig_result = client.generate_auth_sig(siwe_result["siweMessage"])
        auth_sig = auth_sig_result["authSig"]  # Extract the actual authSig object
        print(f"AuthSig generated successfully for {auth_sig.get('address')}")
    except Exception as e:
        print(f"ERROR: Failed to generate auth sig: {e}")
        sys.exit(1)
    
    # Mint the PKP
    print("\n[3/4] Minting PKP...")
    print("This may take 30-60 seconds...")
    
    try:
        # authMethodType 1 = EthWallet
        # scopes = [1] = SignAnything
        mint_result = client.mint_with_auth(
            auth_method={
                "authMethodType": 1,  # EthWallet
                "accessToken": auth_sig,
            },
            scopes=[1]  # SignAnything scope
        )
        
        print(f"Mint result: {mint_result}")
        
        # Check for error
        if "error" in mint_result:
            raise Exception(mint_result["error"].get("message", mint_result["error"]))
        
        pkp_info = mint_result.get("pkp", mint_result)
        
        print("\n" + "=" * 60)
        print("PKP MINTED SUCCESSFULLY!")
        print("=" * 60)
        
        token_id = pkp_info.get('tokenId', pkp_info.get('token_id', 'unknown'))
        public_key = pkp_info.get('publicKey', pkp_info.get('public_key', 'unknown'))
        eth_address = pkp_info.get('ethAddress', pkp_info.get('eth_address', 'unknown'))
        
        print(f"\nPKP Token ID: {token_id}")
        print(f"PKP Public Key: {public_key}")
        print(f"PKP ETH Address: {eth_address}")
        
        # Save to file for reference
        output = {
            "network": LIT_NETWORK,
            "minted_at": datetime.now(timezone.utc).isoformat(),
            "controller_wallet": wallet_address,
            "pkp": {
                "token_id": token_id,
                "public_key": public_key,
                "eth_address": eth_address
            }
        }
        
        output_file = Path(__file__).parent / "pkp_info.json"
        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\nPKP info saved to: {output_file}")
        
        # Print env vars to add
        print("\n" + "-" * 60)
        print("Add these to your .env file:")
        print("-" * 60)
        print(f"LIT_PKP_TOKEN_ID={token_id}")
        print(f"LIT_PKP_PUBLIC_KEY={public_key}")
        print(f"LIT_PKP_ETH_ADDRESS={eth_address}")
        
        print("\n" + "-" * 60)
        print("NEXT STEPS:")
        print("-" * 60)
        print("1. Fund the PKP address with Base Sepolia ETH for gas")
        print("2. Run whitelist_pkp_on_tba.py to authorize PKP on TBA")
        print("3. Test signing with sign_transaction.py")
        
        return pkp_info
        
    except Exception as e:
        print(f"ERROR: Failed to mint PKP: {e}")
        import traceback
        traceback.print_exc()
        print("\nTroubleshooting:")
        print("1. Ensure controller wallet has tstLPX tokens")
        print("2. Get tokens from: https://chronicle-yellowstone-faucet.getlit.dev")
        sys.exit(1)
    finally:
        # Clean up
        try:
            client.disconnect()
        except:
            pass


def main():
    """Entry point."""
    mint_pkp()


if __name__ == "__main__":
    main()
