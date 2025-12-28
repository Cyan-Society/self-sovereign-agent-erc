#!/usr/bin/env python3
"""
Sign transactions using Lit Protocol PKP.

This module provides helper functions for signing transaction hashes
using a Lit Protocol PKP (Programmable Key Pair).

Usage:
    from scripts.lit.sign_transaction import LitSigner
    
    signer = LitSigner()
    await signer.connect()
    
    signature = await signer.sign_transaction_hash(tx_hash)
    
    # Or sign and broadcast
    receipt = await signer.sign_and_send(web3, tx_dict)
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env")

try:
    from lit_python_sdk import connect
except ImportError:
    print("ERROR: lit-python-sdk not installed")
    print("Install with: pip install lit-python-sdk")
    sys.exit(1)

# Load the Lit Action code
LIT_ACTION_PATH = Path(__file__).parent / "lit_action.js"


def load_lit_action_code() -> str:
    """Load the Lit Action JavaScript code."""
    with open(LIT_ACTION_PATH, 'r') as f:
        content = f.read()
    
    # Extract the code from the JS file (between backticks)
    start = content.find('`\n') + 2
    end = content.rfind('\n`')
    if start > 1 and end > start:
        return content[start:end]
    
    # Fallback: return the whole thing
    return content


# The Lit Action code (inline for simplicity)
LIT_ACTION_CODE = """
(async () => {
  try {
    console.log("Kieran's Lit Action executing...");
    
    // Simple policy: trust session sig holder
    const isAuthorized = true;
    
    if (!isAuthorized) {
      Lit.Actions.setResponse({ 
        response: JSON.stringify({
          success: false,
          error: "Unauthorized"
        })
      });
      return;
    }
    
    // Sign the message
    const sigShare = await Lit.Actions.signAndCombineEcdsa({
      toSign: toSign,
      publicKey: publicKey,
      sigName: sigName || "kieran_sig"
    });
    
    Lit.Actions.setResponse({ 
      response: JSON.stringify({
        success: true,
        signature: sigShare,
        timestamp: Date.now()
      })
    });
    
  } catch (error) {
    Lit.Actions.setResponse({ 
      response: JSON.stringify({
        success: false,
        error: error.message
      })
    });
  }
})();
"""


class LitSigner:
    """
    Helper class for signing transactions with Lit Protocol PKP.
    
    Handles connection, session management, and signature generation.
    """
    
    def __init__(
        self,
        controller_key: Optional[str] = None,
        pkp_public_key: Optional[str] = None,
        network: str = "datil-test"
    ):
        """
        Initialize the LitSigner.
        
        Args:
            controller_key: Private key of the PKP controller wallet
            pkp_public_key: Public key of the PKP to use for signing
            network: Lit network to use (datil-test or datil)
        """
        self.controller_key = controller_key or os.getenv("LIT_CONTROLLER_PRIVATE_KEY") or os.getenv("DEPLOYER_PRIVATE_KEY")
        self.pkp_public_key = pkp_public_key or os.getenv("LIT_PKP_PUBLIC_KEY")
        self.network = network
        self.client = None
        self.session_sigs = None
        
        if not self.controller_key:
            raise ValueError("No controller key provided. Set LIT_CONTROLLER_PRIVATE_KEY in .env")
    
    async def connect(self):
        """Connect to Lit Network and initialize the client."""
        print(f"Connecting to Lit Network ({self.network})...")
        
        self.client = connect()
        self.client.set_auth_token(self.controller_key)
        self.client.new(lit_network=self.network, debug=False)
        await self.client.connect()
        
        print(f"Connected! Controller: {self.client.wallet_address}")
        return self
    
    async def get_session_sigs(self, expiration_minutes: int = 10) -> Dict:
        """
        Get session signatures for PKP operations.
        
        Args:
            expiration_minutes: How long the session should be valid
            
        Returns:
            Session signatures dict
        """
        if not self.client:
            await self.connect()
        
        expiration = (datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        session_sigs = self.client.get_session_sigs(
            chain="ethereum",
            expiration=expiration,
            resource_ability_requests=[
                {
                    "resource": {
                        "resource": "*",
                        "resourcePrefix": "lit-pkp",
                    },
                    "ability": "pkp-signing",
                },
                {
                    "resource": {
                        "resource": "*",
                        "resourcePrefix": "lit-litaction",
                    },
                    "ability": "lit-action-execution",
                }
            ]
        )
        
        self.session_sigs = session_sigs
        return session_sigs
    
    async def sign_hash(self, message_hash: bytes, sig_name: str = "kieran_sig") -> Dict:
        """
        Sign a message hash using the PKP.
        
        Args:
            message_hash: The hash to sign (32 bytes)
            sig_name: Name for the signature
            
        Returns:
            Dict containing the signature (r, s, v)
        """
        if not self.pkp_public_key:
            raise ValueError("No PKP public key set. Run mint_pkp.py first and set LIT_PKP_PUBLIC_KEY")
        
        if not self.session_sigs:
            await self.get_session_sigs()
        
        # Convert hash to integer array for Lit Action
        if isinstance(message_hash, str):
            if message_hash.startswith("0x"):
                message_hash = message_hash[2:]
            to_sign = [int(message_hash[i:i+2], 16) for i in range(0, len(message_hash), 2)]
        elif isinstance(message_hash, bytes):
            to_sign = list(message_hash)
        else:
            to_sign = list(message_hash)
        
        # Execute the Lit Action
        result = self.client.execute_js(
            code=LIT_ACTION_CODE,
            js_params={
                "toSign": to_sign,
                "publicKey": self.pkp_public_key,
                "sigName": sig_name
            },
            session_sigs=self.session_sigs
        )
        
        # Parse the response
        response = result.get("response", "{}")
        if isinstance(response, str):
            response = json.loads(response)
        
        if not response.get("success"):
            raise Exception(f"Signing failed: {response.get('error', 'Unknown error')}")
        
        return response.get("signature")
    
    async def sign_transaction(self, tx_dict: Dict, web3) -> bytes:
        """
        Sign a transaction dictionary.
        
        Args:
            tx_dict: Transaction dictionary (to, value, data, etc.)
            web3: Web3 instance for hashing
            
        Returns:
            Signed transaction bytes
        """
        from eth_account import Account
        from eth_account._utils.legacy_transactions import serializable_unsigned_transaction_from_dict
        
        # Ensure required fields
        if 'nonce' not in tx_dict:
            pkp_address = self._get_pkp_address()
            tx_dict['nonce'] = web3.eth.get_transaction_count(pkp_address)
        
        if 'chainId' not in tx_dict:
            tx_dict['chainId'] = web3.eth.chain_id
        
        if 'gas' not in tx_dict:
            tx_dict['gas'] = web3.eth.estimate_gas(tx_dict)
        
        # Get the transaction hash to sign
        unsigned_tx = serializable_unsigned_transaction_from_dict(tx_dict)
        tx_hash = unsigned_tx.hash()
        
        # Sign with PKP
        signature = await self.sign_hash(tx_hash)
        
        # Combine into signed transaction
        # Note: This is simplified - production code should properly encode
        v = signature.get('v', signature.get('recid', 27))
        r = int(signature['r'], 16) if isinstance(signature['r'], str) else signature['r']
        s = int(signature['s'], 16) if isinstance(signature['s'], str) else signature['s']
        
        signed_tx = unsigned_tx.as_signed_transaction(
            v=v,
            r=r,
            s=s
        )
        
        return signed_tx.raw_transaction
    
    def _get_pkp_address(self) -> str:
        """Get the ETH address of the PKP."""
        pkp_address = os.getenv("LIT_PKP_ETH_ADDRESS")
        if not pkp_address:
            raise ValueError("LIT_PKP_ETH_ADDRESS not set in .env")
        return pkp_address


async def demo():
    """Demo function showing how to use LitSigner."""
    print("=" * 60)
    print("Lit Protocol Signing Demo")
    print("=" * 60)
    
    # Initialize signer
    signer = LitSigner()
    await signer.connect()
    
    # Get session sigs
    print("\nGetting session signatures...")
    await signer.get_session_sigs()
    print("Session sigs obtained!")
    
    # Sign a test message
    test_hash = "0x" + "ab" * 32  # Dummy hash
    print(f"\nSigning test hash: {test_hash[:20]}...")
    
    try:
        signature = await signer.sign_hash(bytes.fromhex(test_hash[2:]))
        print(f"Signature obtained!")
        print(f"  r: {signature.get('r', 'N/A')[:20]}...")
        print(f"  s: {signature.get('s', 'N/A')[:20]}...")
        print(f"  v: {signature.get('v', signature.get('recid', 'N/A'))}")
    except Exception as e:
        print(f"Signing failed: {e}")
        print("\nMake sure you have:")
        print("1. Minted a PKP (run mint_pkp.py)")
        print("2. Set LIT_PKP_PUBLIC_KEY in .env")


if __name__ == "__main__":
    asyncio.run(demo())
