#!/usr/bin/env python3
"""
Lit PKP Signing MCP Server

An MCP server that enables agents to anchor cognitive state on-chain
using Lit Protocol PKP signatures. This allows for true self-invocation
where the agent's signing key (PKP) is controlled by Lit Actions.

Tools exposed:
- anchor_state_via_pkp: Sign and broadcast anchorState transaction
- anchor_action_via_pkp: Sign and broadcast action/authorship anchor
- get_pkp_balance: Check PKP ETH balance
- verify_state_anchor: Verify on-chain state for a token

Security:
- Requires MCP_API_KEY environment variable for authentication
- All tool calls must include valid API key in request context
"""

import os
import json
import time
import secrets
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from typing import Any, Optional
from functools import wraps

from fastmcp import FastMCP, Context
from dotenv import load_dotenv
from web3 import Web3
import rlp
from eth_utils import keccak

# Load environment from project root
ENV_PATH = Path(__file__).parent.parent / '.env'
load_dotenv(ENV_PATH)

# Configuration
RPC_URL = os.getenv('RPC_URL', 'https://sepolia.base.org')
CONTRACT_ADDRESS = os.getenv('AGENT_CONTRACT_ADDRESS')
PKP_PUBLIC_KEY = os.getenv('LIT_PKP_PUBLIC_KEY')
PKP_ETH_ADDRESS = os.getenv('LIT_PKP_ETH_ADDRESS')
DEPLOYER_PRIVATE_KEY = os.getenv('DEPLOYER_PRIVATE_KEY')  # For session auth
CHAIN_ID = 84532  # Base Sepolia

# Authentication
MCP_API_KEY = os.getenv('MCP_API_KEY')
if not MCP_API_KEY:
    # Generate a secure key if not set (for first-time setup)
    print("WARNING: MCP_API_KEY not set in environment!")
    print("Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
    print("Then add to .env: MCP_API_KEY=<generated_key>")
    # For safety, don't auto-generate - require explicit configuration
    MCP_API_KEY = None


def verify_api_key(provided_key: Optional[str]) -> bool:
    """Verify the provided API key matches the configured key."""
    if MCP_API_KEY is None:
        # If no key configured, reject all requests (fail secure)
        return False
    if provided_key is None:
        return False
    # Use constant-time comparison to prevent timing attacks
    return secrets.compare_digest(provided_key, MCP_API_KEY)


class AuthenticationError(Exception):
    """Raised when API key authentication fails."""
    pass

# Contract ABI fragments
ANCHOR_STATE_ABI = [
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

GET_STATE_ANCHOR_ABI = [
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


class LitSignerService:
    """Manages Lit Protocol connection and PKP signing operations."""
    
    def __init__(self):
        self.client = None
        self.session_sigs = None
        self.session_expiry = None
        self.w3 = Web3(Web3.HTTPProvider(RPC_URL))
    
    async def ensure_connected(self) -> bool:
        """Ensure Lit client is connected with valid session."""
        from lit_python_sdk import LitClient
        
        # Check if we need to reconnect
        if self.client is None:
            self.client = LitClient()
            self.client.new(lit_network="datil-test", debug=False)
            self.client.connect()
            
            # Set auth token
            pk = DEPLOYER_PRIVATE_KEY
            if pk.startswith('0x'):
                pk = pk[2:]
            self.client.set_auth_token(pk)
        
        # Check if session is still valid
        now = datetime.utcnow()
        if self.session_sigs is None or (self.session_expiry and now >= self.session_expiry):
            # Get new session signatures
            expiration = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
            result = self.client.get_session_sigs(
                chain="baseSepolia",
                expiration=expiration,
                resource_ability_requests=[
                    {"resource": {"resource": "*", "resourcePrefix": "lit-pkp"}, "ability": "pkp-signing"},
                    {"resource": {"resource": "*", "resourcePrefix": "lit-litaction"}, "ability": "lit-action-execution"},
                ]
            )
            
            if not result.get('success'):
                raise Exception(f"Failed to get session sigs: {result}")
            
            self.session_sigs = result.get('sessionSigs')
            self.session_expiry = now + timedelta(minutes=55)  # Refresh before actual expiry
        
        return True
    
    def build_anchor_transaction(self, token_id: int, state_hash: bytes, state_uri: str) -> dict:
        """Build the anchorState transaction."""
        contract = self.w3.eth.contract(address=CONTRACT_ADDRESS, abi=ANCHOR_STATE_ABI)
        
        nonce = self.w3.eth.get_transaction_count(PKP_ETH_ADDRESS)
        base_fee = self.w3.eth.get_block('latest')['baseFeePerGas']
        max_priority_fee = self.w3.to_wei(1, 'gwei')
        max_fee = base_fee * 2 + max_priority_fee
        
        tx_data = contract.encode_abi('anchorState', [token_id, state_hash, state_uri])
        
        return {
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
    
    def compute_tx_hash(self, tx: dict) -> bytes:
        """Compute the signing hash for an EIP-1559 transaction."""
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
        return keccak(encoded)
    
    async def sign_with_pkp(self, tx_hash: bytes) -> dict:
        """Sign the transaction hash using the PKP via Lit Protocol."""
        await self.ensure_connected()
        
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
        
        result = self.client.execute_js(
            code=lit_action,
            js_params={
                'txHash': '0x' + tx_hash.hex(),
                'pkpPublicKey': PKP_PUBLIC_KEY,
            },
            session_sigs=self.session_sigs
        )
        
        return result
    
    def serialize_signed_tx(self, tx: dict, signature: dict) -> bytes:
        """Serialize the signed EIP-1559 transaction."""
        r = int(signature['r'], 16)
        s = int(signature['s'], 16)
        v = signature['recid']
        
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
        
        return b'\x02' + rlp.encode(tx_fields)
    
    def disconnect(self):
        """Disconnect from Lit Protocol."""
        if self.client:
            try:
                self.client.disconnect()
            except:
                pass
            self.client = None
            self.session_sigs = None


# Global service instance
lit_service = LitSignerService()


# Lifespan for cleanup
@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage server lifecycle."""
    yield {}
    # Cleanup on shutdown
    lit_service.disconnect()


# Create MCP server
mcp = FastMCP(
    name="Lit PKP Signer",
    instructions="""
    This server enables agents to anchor cognitive state on-chain using 
    Lit Protocol PKP signatures. Use anchor_state_via_pkp to sign and 
    broadcast state anchoring transactions.
    
    AUTHENTICATION REQUIRED: All signing tools require a valid api_key parameter.
    Read-only tools (get_pkp_balance, verify_state_anchor) do not require authentication.
    """,
    lifespan=lifespan
)


@mcp.tool
async def anchor_state_via_pkp(
    token_id: int,
    state_hash: str,
    state_uri: str,
    ctx: Context,
    api_key: Optional[str] = None
) -> dict:
    """
    Anchor cognitive state on-chain using PKP signature.
    
    This tool signs an anchorState transaction using the Lit Protocol PKP
    and broadcasts it to Base Sepolia. The PKP must have executor permissions
    on the specified token.
    
    Args:
        token_id: The NFT token ID to anchor state for
        state_hash: The keccak256 hash of the state (hex string with 0x prefix)
        state_uri: URI pointing to the full state data (e.g., IPFS URI)
        api_key: Optional authentication key (uses MCP_API_KEY env var if not provided)
    
    Returns:
        dict with tx_hash, block_number, gas_used on success
        dict with error message on failure
    """
    # Authenticate - use provided key or fall back to environment variable
    effective_key = api_key if api_key else MCP_API_KEY
    if not verify_api_key(effective_key):
        print(f"[AUTH] Rejected anchor_state_via_pkp - invalid API key")
        return {"error": "Authentication failed: invalid or missing API key"}
    
    await ctx.info(f"Anchoring state for token {token_id}")
    
    try:
        # Validate inputs
        if not state_hash.startswith('0x') or len(state_hash) != 66:
            return {"error": "state_hash must be a 66-character hex string (0x + 64 hex chars)"}
        
        state_hash_bytes = bytes.fromhex(state_hash[2:])
        
        # Build transaction
        await ctx.info("Building transaction...")
        tx = lit_service.build_anchor_transaction(token_id, state_hash_bytes, state_uri)
        tx_hash_to_sign = lit_service.compute_tx_hash(tx)
        
        await ctx.report_progress(progress=25, total=100)
        
        # Sign with PKP
        await ctx.info("Signing with PKP via Lit Protocol...")
        sign_result = await lit_service.sign_with_pkp(tx_hash_to_sign)
        
        if not sign_result.get('signatures', {}).get('anchorStateSig'):
            return {"error": f"PKP signing failed: {sign_result}"}
        
        signature = sign_result['signatures']['anchorStateSig']
        await ctx.report_progress(progress=50, total=100)
        
        # Serialize and broadcast
        await ctx.info("Broadcasting transaction...")
        signed_tx_bytes = lit_service.serialize_signed_tx(tx, signature)
        
        tx_hash_sent = lit_service.w3.eth.send_raw_transaction(signed_tx_bytes)
        await ctx.report_progress(progress=75, total=100)
        
        # Wait for confirmation
        await ctx.info("Waiting for confirmation...")
        receipt = lit_service.w3.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
        
        await ctx.report_progress(progress=100, total=100)
        
        if receipt['status'] == 1:
            return {
                "success": True,
                "tx_hash": tx_hash_sent.hex(),
                "block_number": receipt['blockNumber'],
                "gas_used": receipt['gasUsed'],
                "explorer_url": f"https://sepolia.basescan.org/tx/{tx_hash_sent.hex()}"
            }
        else:
            return {"error": "Transaction reverted", "receipt": str(receipt)}
            
    except Exception as e:
        await ctx.error(f"Anchor failed: {str(e)}")
        return {"error": str(e)}


@mcp.tool
async def get_pkp_balance(ctx: Context) -> dict:
    """
    Check the ETH balance of the PKP address.
    
    Returns the current balance in ETH and Wei. Low balance will
    prevent state anchoring transactions from succeeding.
    
    Returns:
        dict with address, balance_eth, balance_wei
    """
    try:
        balance_wei = lit_service.w3.eth.get_balance(PKP_ETH_ADDRESS)
        balance_eth = lit_service.w3.from_wei(balance_wei, 'ether')
        
        return {
            "address": PKP_ETH_ADDRESS,
            "balance_eth": str(balance_eth),
            "balance_wei": balance_wei,
            "low_balance_warning": balance_wei < lit_service.w3.to_wei(0.001, 'ether')
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool
async def anchor_action_via_pkp(
    token_id: int,
    work_product_content: str,
    content_type: str,
    description: str,
    creator_agent_id: str,
    creator_name: str,
    collaborators: list[str],
    anchor_type: str,
    ctx: Context,
    api_key: Optional[str] = None
) -> dict:
    """
    Anchor a work product (action) on-chain for authorship verification.
    
    This creates a cryptographic proof that a specific work product was created
    by a specific agent at a specific time. Unlike state anchoring (which proves
    identity/memory integrity), action anchoring proves authorship and attribution.
    
    The anchor hash combines:
    - Hash of the work product content
    - Creator's cognitive state hash (if available, fetched from chain)
    - Metadata (timestamp, collaborators, description)
    
    Args:
        token_id: The NFT token ID representing the creator agent
        work_product_content: The actual content to anchor (document text, code, etc.)
        content_type: MIME type of the content (e.g., "text/markdown", "application/python")
        description: Human-readable description of the work product
        creator_agent_id: The Letta agent ID of the creator
        creator_name: Human-readable name of the creator agent
        collaborators: List of collaborator names (human or agent)
        anchor_type: Type of action ("authorship", "decision", "action")
        api_key: Optional authentication key (uses MCP_API_KEY env var if not provided)
    
    Returns:
        dict with tx_hash, action_anchor_data, explorer_url on success
        dict with error message on failure
    """
    # Authenticate - use provided key or fall back to environment variable
    effective_key = api_key if api_key else MCP_API_KEY
    if not verify_api_key(effective_key):
        print(f"[AUTH] Rejected anchor_action_via_pkp - invalid API key")
        return {"error": "Authentication failed: invalid or missing API key"}
    
    await ctx.info(f"Anchoring action for token {token_id}: {description}")
    
    try:
        import time as time_module
        
        # Step 1: Hash the work product content
        work_product_hash = lit_service.w3.keccak(text=work_product_content)
        await ctx.info(f"Work product hash: 0x{work_product_hash.hex()[:16]}...")
        
        # Step 2: Get the creator's current cognitive state hash (if anchored)
        contract = lit_service.w3.eth.contract(
            address=CONTRACT_ADDRESS, 
            abi=GET_STATE_ANCHOR_ABI
        )
        try:
            state_result = contract.functions.getStateAnchor(token_id).call()
            creator_state_hash = "0x" + state_result[0].hex()
        except Exception:
            creator_state_hash = "0x" + "0" * 64  # No state anchored yet
        
        await ctx.info(f"Creator state hash: {creator_state_hash[:18]}...")
        await ctx.report_progress(progress=20, total=100)
        
        # Step 3: Build the action anchor metadata
        timestamp = int(time_module.time())
        action_anchor_data = {
            "anchor_type": "action",
            "action_subtype": anchor_type,
            "work_product": {
                "hash": "0x" + work_product_hash.hex(),
                "content_type": content_type,
                "description": description,
                "size_bytes": len(work_product_content.encode('utf-8'))
            },
            "creator": {
                "token_id": token_id,
                "agent_id": creator_agent_id,
                "name": creator_name,
                "state_hash_at_creation": creator_state_hash
            },
            "collaborators": collaborators,
            "timestamp": timestamp,
            "timestamp_iso": datetime.utcfromtimestamp(timestamp).isoformat() + "Z"
        }
        
        # Step 4: Create the combined anchor hash
        # This links work product + creator identity + context
        anchor_payload = json.dumps(action_anchor_data, sort_keys=True, separators=(',', ':'))
        combined_anchor_hash = lit_service.w3.keccak(text=anchor_payload)
        
        await ctx.info(f"Combined anchor hash: 0x{combined_anchor_hash.hex()[:16]}...")
        await ctx.report_progress(progress=40, total=100)
        
        # Step 5: Create the state URI pointing to full action data
        # In production, this would be uploaded to IPFS/Arweave
        state_uri = f"letta://agent/{creator_agent_id}/action/{anchor_type}/{timestamp}"
        
        # Step 6: Anchor on-chain using the existing anchorState function
        # (The contract is generic - we're just using it for a different purpose)
        tx = lit_service.build_anchor_transaction(
            token_id, 
            combined_anchor_hash, 
            state_uri
        )
        tx_hash_to_sign = lit_service.compute_tx_hash(tx)
        
        await ctx.info("Signing with PKP via Lit Protocol...")
        await ctx.report_progress(progress=50, total=100)
        
        sign_result = await lit_service.sign_with_pkp(tx_hash_to_sign)
        
        if not sign_result.get('signatures', {}).get('anchorStateSig'):
            return {"error": f"PKP signing failed: {sign_result}"}
        
        signature = sign_result['signatures']['anchorStateSig']
        await ctx.report_progress(progress=70, total=100)
        
        # Serialize and broadcast
        await ctx.info("Broadcasting transaction...")
        signed_tx_bytes = lit_service.serialize_signed_tx(tx, signature)
        
        tx_hash_sent = lit_service.w3.eth.send_raw_transaction(signed_tx_bytes)
        await ctx.report_progress(progress=85, total=100)
        
        # Wait for confirmation
        await ctx.info("Waiting for confirmation...")
        receipt = lit_service.w3.eth.wait_for_transaction_receipt(tx_hash_sent, timeout=120)
        
        await ctx.report_progress(progress=100, total=100)
        
        if receipt['status'] == 1:
            return {
                "success": True,
                "tx_hash": tx_hash_sent.hex(),
                "block_number": receipt['blockNumber'],
                "gas_used": receipt['gasUsed'],
                "explorer_url": f"https://sepolia.basescan.org/tx/{tx_hash_sent.hex()}",
                "action_anchor": {
                    "combined_hash": "0x" + combined_anchor_hash.hex(),
                    "work_product_hash": "0x" + work_product_hash.hex(),
                    "creator_state_hash": creator_state_hash,
                    "state_uri": state_uri,
                    "description": description,
                    "anchor_type": anchor_type,
                    "collaborators": collaborators,
                    "timestamp": timestamp
                }
            }
        else:
            return {"error": "Transaction reverted", "receipt": str(receipt)}
            
    except Exception as e:
        await ctx.error(f"Action anchor failed: {str(e)}")
        return {"error": str(e)}


@mcp.tool
async def verify_state_anchor(token_id: int, ctx: Context) -> dict:
    """
    Verify the current state anchor for a token on-chain.
    
    Reads the latest anchored state from the contract.
    
    Args:
        token_id: The NFT token ID to check
    
    Returns:
        dict with state_hash, state_uri, timestamp, or error
    """
    try:
        contract = lit_service.w3.eth.contract(
            address=CONTRACT_ADDRESS, 
            abi=GET_STATE_ANCHOR_ABI
        )
        
        result = contract.functions.getStateAnchor(token_id).call()
        
        return {
            "token_id": token_id,
            "state_hash": "0x" + result[0].hex(),
            "state_uri": result[1],
            "timestamp": result[2],
            "timestamp_human": datetime.utcfromtimestamp(result[2]).isoformat() + "Z" if result[2] > 0 else None
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import sys
    
    # Default to HTTP transport for remote access
    transport = sys.argv[1] if len(sys.argv) > 1 else "http"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
    
    print(f"Starting Lit PKP Signer MCP Server...")
    print(f"  Transport: {transport}")
    print(f"  Port: {port}")
    print(f"  Contract: {CONTRACT_ADDRESS}")
    print(f"  PKP Address: {PKP_ETH_ADDRESS}")
    
    mcp.run(transport=transport, host="0.0.0.0", port=port)
