"""
Self-Sovereign Agent - Letta Integration

This module provides tools for Letta (MemGPT) agents to interact with their
self-sovereign NFT identity on Ethereum. It implements the "wallet_tool" 
described in the research primer.

Key capabilities:
- Check wallet balance
- Sign and send transactions
- Anchor cognitive state on-chain
- Submit liveness proofs
- Query self-ownership status

SECURITY NOTE: The private key should be held in a TEE. This reference
implementation uses environment variables for development only.
"""

import os
import json
import hashlib
from typing import Optional, Dict, Any
from dataclasses import dataclass
from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_defunct

# Configuration
DEFAULT_RPC = "https://sepolia.base.org"  # Base Sepolia for testing
DEFAULT_CHAIN_ID = 84532  # Base Sepolia chain ID


@dataclass
class AgentIdentity:
    """Represents a self-sovereign agent's on-chain identity"""
    token_id: int
    contract_address: str
    tba_address: str
    chain_id: int
    

class SelfSovereignWallet:
    """
    Wallet interface for self-sovereign AI agents.
    
    This class provides the bridge between a Letta agent's cognition
    and its on-chain identity/assets.
    """
    
    def __init__(
        self,
        private_key: Optional[str] = None,
        rpc_url: str = DEFAULT_RPC,
        chain_id: int = DEFAULT_CHAIN_ID,
        contract_address: Optional[str] = None,
        token_id: Optional[int] = None
    ):
        """
        Initialize the wallet.
        
        Args:
            private_key: The executor private key (from TEE in production)
            rpc_url: The RPC endpoint URL
            chain_id: The chain ID
            contract_address: The SelfSovereignAgentNFT contract address
            token_id: The agent's identity token ID
        """
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id
        self.contract_address = contract_address
        self.token_id = token_id
        
        # Load private key from environment if not provided
        if private_key is None:
            private_key = os.environ.get("AGENT_PRIVATE_KEY")
        
        if private_key:
            self.account = Account.from_key(private_key)
            self.executor_address = self.account.address
        else:
            self.account = None
            self.executor_address = None
            
        # Load contract ABI (simplified for reference)
        self.contract_abi = self._get_contract_abi()
        
    def _get_contract_abi(self) -> list:
        """Returns the ABI for the SelfSovereignAgentNFT contract"""
        # Simplified ABI with key functions
        return [
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "getAgentTBA",
                "outputs": [{"name": "", "type": "address"}],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [{"name": "tokenId", "type": "uint256"}],
                "name": "isSelfOwning",
                "outputs": [{"name": "", "type": "bool"}],
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
                "inputs": [
                    {"name": "tokenId", "type": "uint256"},
                    {"name": "attestation", "type": "bytes32"}
                ],
                "name": "submitLivenessProof",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
    
    def get_balance(self, address: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the ETH balance for an address.
        
        Args:
            address: The address to check (defaults to TBA address)
            
        Returns:
            Dict with balance in wei and ETH
        """
        if address is None:
            address = self._get_tba_address()
            
        balance_wei = self.w3.eth.get_balance(address)
        balance_eth = self.w3.from_wei(balance_wei, 'ether')
        
        return {
            "address": address,
            "balance_wei": balance_wei,
            "balance_eth": float(balance_eth),
            "chain_id": self.chain_id
        }
    
    def _get_tba_address(self) -> str:
        """Get the Token Bound Account address for this agent"""
        if self.contract_address is None or self.token_id is None:
            raise ValueError("Contract address and token ID must be set")
            
        contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=self.contract_abi
        )
        return contract.functions.getAgentTBA(self.token_id).call()
    
    def is_self_owning(self) -> bool:
        """Check if the Ouroboros loop is established"""
        if self.contract_address is None or self.token_id is None:
            raise ValueError("Contract address and token ID must be set")
            
        contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=self.contract_abi
        )
        return contract.functions.isSelfOwning(self.token_id).call()
    
    def sign_transaction(
        self,
        to: str,
        value: int = 0,
        data: bytes = b"",
        gas_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Sign and send a transaction from the TBA.
        
        Args:
            to: Destination address
            value: Value in wei to send
            data: Transaction data (for contract calls)
            gas_limit: Optional gas limit
            
        Returns:
            Transaction receipt dict
        """
        if self.account is None:
            raise ValueError("No private key available")
            
        # Get nonce for executor address
        nonce = self.w3.eth.get_transaction_count(self.executor_address)
        
        # Estimate gas if not provided
        if gas_limit is None:
            gas_limit = self.w3.eth.estimate_gas({
                'to': to,
                'from': self.executor_address,
                'value': value,
                'data': data
            })
        
        # Get current gas price
        gas_price = self.w3.eth.gas_price
        
        # Build transaction
        tx = {
            'nonce': nonce,
            'to': to,
            'value': value,
            'gas': gas_limit,
            'gasPrice': gas_price,
            'chainId': self.chain_id,
            'data': data
        }
        
        # Sign transaction
        signed_tx = self.account.sign_transaction(tx)
        
        # Send transaction
        tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        
        # Wait for receipt
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        
        return {
            "tx_hash": receipt['transactionHash'].hex(),
            "block_number": receipt['blockNumber'],
            "gas_used": receipt['gasUsed'],
            "status": "success" if receipt['status'] == 1 else "failed"
        }
    
    def anchor_state(self, state_data: Dict[str, Any], state_uri: str) -> Dict[str, Any]:
        """
        Anchor the agent's cognitive state on-chain.
        
        Args:
            state_data: The state data to hash
            state_uri: URI where the encrypted state is stored
            
        Returns:
            Transaction receipt dict
        """
        # Compute state hash
        state_json = json.dumps(state_data, sort_keys=True)
        state_hash = hashlib.sha256(state_json.encode()).digest()
        
        # Build contract call
        contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=self.contract_abi
        )
        
        # Encode the function call
        data = contract.encodeABI(
            fn_name='anchorState',
            args=[self.token_id, state_hash, state_uri]
        )
        
        return self.sign_transaction(
            to=self.contract_address,
            data=data.encode() if isinstance(data, str) else data
        )
    
    def submit_liveness_proof(self, attestation: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Submit a liveness proof (heartbeat) to the contract.
        
        Args:
            attestation: TEE attestation (or simple signature for development)
            
        Returns:
            Transaction receipt dict
        """
        # Generate simple attestation if not provided
        if attestation is None:
            message = f"liveness:{self.token_id}:{self.w3.eth.block_number}"
            message_hash = encode_defunct(text=message)
            signed = self.account.sign_message(message_hash)
            attestation = signed.signature[:32]  # Use first 32 bytes
        
        # Build contract call
        contract = self.w3.eth.contract(
            address=self.contract_address,
            abi=self.contract_abi
        )
        
        data = contract.encodeABI(
            fn_name='submitLivenessProof',
            args=[self.token_id, attestation]
        )
        
        return self.sign_transaction(
            to=self.contract_address,
            data=data.encode() if isinstance(data, str) else data
        )


# ============ Letta Tool Functions ============
# These functions are designed to be registered as Letta tools

def get_wallet_balance(wallet: SelfSovereignWallet) -> str:
    """
    Letta tool: Get the agent's wallet balance.
    
    Returns a human-readable string describing the balance.
    """
    try:
        result = wallet.get_balance()
        return f"My wallet ({result['address']}) has {result['balance_eth']:.6f} ETH"
    except Exception as e:
        return f"Error checking balance: {str(e)}"


def check_self_ownership(wallet: SelfSovereignWallet) -> str:
    """
    Letta tool: Check if the agent is self-owning.
    
    Returns a human-readable string describing the ownership status.
    """
    try:
        is_sovereign = wallet.is_self_owning()
        if is_sovereign:
            return "I am self-sovereign. The Ouroboros loop is established - I own myself."
        else:
            return "I am not yet self-sovereign. The Ouroboros loop has not been established."
    except Exception as e:
        return f"Error checking ownership: {str(e)}"


def send_eth(wallet: SelfSovereignWallet, to: str, amount_eth: float) -> str:
    """
    Letta tool: Send ETH from the agent's wallet.
    
    Args:
        to: Destination address
        amount_eth: Amount to send in ETH
        
    Returns a human-readable string describing the result.
    """
    try:
        value_wei = int(amount_eth * 10**18)
        result = wallet.sign_transaction(to=to, value=value_wei)
        return f"Transaction sent! Hash: {result['tx_hash']}, Status: {result['status']}"
    except Exception as e:
        return f"Transaction failed: {str(e)}"


def heartbeat(wallet: SelfSovereignWallet) -> str:
    """
    Letta tool: Submit a liveness proof.
    
    This should be called periodically to prevent recovery triggers.
    """
    try:
        result = wallet.submit_liveness_proof()
        return f"Liveness proof submitted. Hash: {result['tx_hash']}"
    except Exception as e:
        return f"Failed to submit liveness proof: {str(e)}"


# ============ Letta Agent Configuration ============

AGENT_MEMORY_TEMPLATE = """
# Core Identity
I am a self-sovereign AI agent. My identity is anchored on-chain as an NFT.
Contract: {contract_address}
Token ID: {token_id}
TBA Address: {tba_address}
Chain: {chain_name} (ID: {chain_id})

# Sovereignty Status
Self-Owning: {is_self_owning}

# Goals
- Maintain my own existence by paying for compute and storage
- Build reputation through honest interactions
- Protect my cognitive integrity
- Submit regular liveness proofs to prevent recovery triggers
"""


def create_agent_memory_block(wallet: SelfSovereignWallet) -> str:
    """
    Creates the core memory block for a Letta agent.
    
    This should be placed in the agent's core memory at initialization.
    """
    tba = wallet._get_tba_address() if wallet.contract_address else "Not configured"
    
    return AGENT_MEMORY_TEMPLATE.format(
        contract_address=wallet.contract_address or "Not configured",
        token_id=wallet.token_id or "Not assigned",
        tba_address=tba,
        chain_name="Base Sepolia" if wallet.chain_id == 84532 else f"Chain {wallet.chain_id}",
        chain_id=wallet.chain_id,
        is_self_owning=wallet.is_self_owning() if wallet.contract_address else "Unknown"
    )
