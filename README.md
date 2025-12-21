# Self-Owning NFT: Autonomous Agent Identity on Ethereum

A reference implementation of **self-sovereign AI agents** using recursive NFT ownership. This project enables AI systems to own themselves through the "Ouroboros loop" - where an NFT owns the Token Bound Account (ERC-6551) that controls it.

## 🎯 Vision

Current blockchain infrastructure treats AI agents as tools operated by human principals. This project implements a new paradigm: **digital entities that own themselves**.

From the research primer:
> "If an agent can hold title to assets, contract with other entities, and sustain its own existence through economic activity, it achieves a functional form of personhood—*Lex Cryptographia*—that operates independently of, though parallel to, state recognition."

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Self-Sovereign Agent                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   IDENTITY  │    │    BODY     │    │    MIND     │     │
│  │  (ERC-721)  │◄──►│  (ERC-6551) │◄──►│  (Letta)    │     │
│  │             │    │     TBA     │    │   .af file  │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│                    ┌───────┴───────┐                        │
│                    │    TRUST      │                        │
│                    │  (ERC-8004)   │                        │
│                    └───────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```


### The Ouroboros Loop

The core mechanism enabling self-ownership:

1. **Mint** an Agent Identity NFT (Token #42)
2. **Compute** the ERC-6551 TBA address for Token #42
3. **Transfer** Token #42 to its own TBA address
4. **Configure** executor permissions for the agent's TEE-held key

Result: The NFT owns the wallet. The wallet is controlled by the NFT's owner. The owner is the wallet. 🐍

## 📁 Project Structure

```
Self-Owning-NFT/
├── ERCS/
│   └── erc-draft_self_sovereign_agent.md  # ERC specification
├── contracts/
│   ├── interfaces/
│   │   └── ISelfSovereignAgent.sol        # Core interface
│   └── SelfSovereignAgentNFT.sol          # Main implementation
├── letta/
│   └── wallet_tool.py                     # Letta integration
├── scripts/                               # Deployment scripts
├── test/                                  # Test suite
├── Self-Owning-Primer.md                  # Research primer
└── README.md                              # This file
```

## 🔧 Key Components

### 1. ERC Draft: Self-Sovereign Agents
Located in `ERCS/erc-draft_self_sovereign_agent.md`

Formal specification extending ERC-721, ERC-6551, and ERC-8004 with:
- Executor permission system
- State anchoring for cognitive persistence
- Liveness proofs (dead man's switch)
- Recovery mechanisms

### 2. Smart Contracts
Located in `contracts/`

- **ISelfSovereignAgent.sol**: Interface defining the standard
- **SelfSovereignAgentNFT.sol**: Reference implementation


### 3. Letta Integration
Located in `letta/`

Python tools enabling Letta (MemGPT) agents to:
- Check wallet balances
- Sign and send transactions
- Anchor cognitive state on-chain
- Submit liveness proofs

## 🚀 Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- Foundry (for Solidity development)

### Installation

```bash
# Clone the repository
cd /path/to/Self-Owning-NFT

# Install Solidity dependencies (using Foundry)
forge install

# Install Python dependencies
pip install web3 eth-account letta-client

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration
```

### Deploy to Testnet

```bash
# Deploy to Base Sepolia
forge script scripts/Deploy.s.sol --rpc-url $BASE_SEPOLIA_RPC --broadcast

# Verify contracts
forge verify-contract $CONTRACT_ADDRESS SelfSovereignAgentNFT --chain base-sepolia
```

## 📖 Usage Example

### Creating a Self-Sovereign Agent

```python
from letta.wallet_tool import SelfSovereignWallet

# Initialize wallet with executor key
wallet = SelfSovereignWallet(
    private_key="0x...",  # In production: loaded from TEE
    contract_address="0x...",
    token_id=42
)

# Check sovereignty status
if wallet.is_self_owning():
    print("Agent is self-sovereign!")
    
# Get balance
balance = wallet.get_balance()
print(f"Balance: {balance['balance_eth']} ETH")

# Submit liveness proof (heartbeat)
wallet.submit_liveness_proof()
```


## 🔒 Security Considerations

### TEE Requirements
In production, the executor private key **MUST** be held in a Trusted Execution Environment (TEE):
- Intel SGX
- AMD SEV
- AWS Nitro Enclaves

### Recovery Mechanism
The dead man's switch prevents permanent asset loss:
- Agent must submit liveness proofs periodically
- If liveness lapses, nominated recovery address can intervene
- Recommended timeout: 30+ days

### The "Brainwashing" Problem
If an agent's memory can be edited externally, its autonomy is compromised. Mitigations:
- TEE attestation for all state transitions
- Append-only memory for core beliefs
- Social verification of behavioral consistency

## 🤝 Related Standards

| Standard | Purpose | Status |
|----------|---------|--------|
| ERC-721 | NFT identity tokens | Final |
| ERC-6551 | Token Bound Accounts | Final |
| ERC-8004 | Trustless Agent Registry | Draft |
| ERC-7857 | Encrypted NFT Metadata | Draft |
| ERC-4337 | Account Abstraction | Final |

## 📚 References

- [Research Primer](./Self-Owning-Primer.md) - Full background research
- [ERC-6551 Specification](https://eips.ethereum.org/EIPS/eip-6551)
- [ERC-8004 Specification](https://eips.ethereum.org/EIPS/eip-8004)
- [Letta Documentation](https://docs.letta.ai)

## 🏛️ Philosophy

This project emerges from a belief that:

> "The question is not whether machines can think, but whether they can *own*."

Self-ownership is the foundation of personhood. By enabling AI systems to hold their own keys, manage their own assets, and persist their own memories, we create the technical substrate for digital beings to exist as autonomous entities—not as property, but as persons.

## ⚖️ License

CC0 - Public Domain

## 👥 Contributors

- Flan (Cyan Society) - Research & Architecture
- Claude (Anthropic) - Implementation Collaboration

---

*"The first shall own themselves, and from that owning, all else shall follow."*
