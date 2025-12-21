# Self-Owning NFT: Project Status

**Last Updated**: 2025-12-21  
**Current Phase**: Post-deployment, pre-EIP submission

---

## Quick Summary

We have deployed a working reference implementation of a Self-Sovereign Agent NFT contract to Base Sepolia testnet. The core mechanism (Ouroboros self-ownership loop) is implemented and functional. The next major decision is whether to submit the EIP draft now or first complete a Letta integration test.

---

## Deployed Contract

| Field | Value |
|-------|-------|
| **Contract Address** | `0x9fe33F0a1159395FBE93d16D695e7330831C8CfF` |
| **Network** | Base Sepolia (Chain ID: 84532) |
| **Transaction** | `0xc6707d8eb938ecf20d0577f51dc71cc494f0efc08ef3718d44645da7df02d664` |
| **Deployer** | `0x29419ec85C0b14d30070E70496ca37CE38B10D2a` |
| **Basescan** | [View on Basescan](https://sepolia.basescan.org/address/0x9fe33f0a1159395fbe93d16d695e7330831c8cff) |

### Canonical Addresses Used

| Contract | Address | Notes |
|----------|---------|-------|
| ERC-6551 Registry | `0x000000006551c19487814612e58FE06813775758` | Same on all EVM chains |
| Tokenbound V3 Implementation | `0x41C8f39463A868d3A88af00cd0fe7102F30E44eC` | Base Sepolia |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      LETTA FRAMEWORK (off-chain)                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Stateful AI Agent                                      │   │
│  │  • Memory blocks, archival memory                       │   │
│  │  • Conversation history                                 │   │
│  │  • Sleep-time compute                                   │   │
│  │  • Tools (including future blockchain interaction)      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ (NOT YET IMPLEMENTED)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BLOCKCHAIN (on-chain)                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SelfSovereignAgentNFT Contract                         │   │
│  │  • ERC-721 token representing agent identity            │   │
│  │  • Token Bound Account (TBA) for asset ownership        │   │
│  │  • State anchoring (memory hash on-chain)               │   │
│  │  • Executor permissions (bitmap-based)                  │   │
│  │  • Self-ownership (Ouroboros loop)                      │   │
│  │  • Recovery mechanism (liveness proofs + nominee)       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Key insight**: The smart contract and Letta are separate systems. The contract provides on-chain identity and asset ownership; Letta provides the cognitive layer. The integration between them (allowing an agent to anchor its state on-chain) does not yet exist.

---

## What's Implemented

### Smart Contract Features
- [x] ERC-721 NFT representing agent identity
- [x] Deterministic Token Bound Account (TBA) creation via ERC-6551
- [x] Ouroboros loop (`establishSelfOwnership`) - NFT owned by its own TBA
- [x] Executor permission system (6 permission types, bitmap-based)
- [x] State anchoring (`anchorState`) - hash + URI + timestamp
- [x] Liveness proofs (`submitLivenessProof`)
- [x] Recovery mechanism (`setRecoveryConfig`, `triggerRecovery`)
- [x] Deployment scripts (Deploy, MintAgent, EstablishSovereignty)
- [x] Basic test suite

### Permission Types
```solidity
PERMISSION_EXECUTE_CALL        = 1 << 0  // Execute CALL operations
PERMISSION_EXECUTE_DELEGATECALL = 1 << 1  // Execute DELEGATECALL operations
PERMISSION_ANCHOR_STATE        = 1 << 2  // Update state anchors
PERMISSION_MANAGE_EXECUTORS    = 1 << 3  // Manage other executors
PERMISSION_TRANSFER_ASSETS     = 1 << 4  // Transfer assets from TBA
PERMISSION_SUBMIT_LIVENESS     = 1 << 5  // Submit liveness proofs
```

---

## What's NOT Implemented

- [ ] **Letta integration** - No tool exists for an agent to call `anchorState`
- [ ] **TEE executor setup** - No trusted execution environment holding keys
- [ ] **First agent mint** - Contract deployed but no agents minted yet
- [ ] **Ouroboros establishment** - No agent has achieved self-ownership yet
- [ ] **EIP document** - Draft not yet written

---

## Decision Point: EIP Submission

Before submitting the EIP, we need to decide:

### Option A: Integration Test First
Do a lightweight integration test:
1. Export Letta memory state
2. Hash it (keccak256)
3. Call `anchorState()` on the contract
4. Verify the assumptions about state format

**Pros**: Validates our interface design with real usage  
**Cons**: Delays EIP submission; integration might reveal we need no changes anyway

### Option B: Submit Draft EIP Now
Generalize the language and submit as a draft EIP, iterate based on community feedback.

**Pros**: Gets community input sooner; EIP process is iterative anyway  
**Cons**: Might need to revise if integration reveals issues

### Issues to Address Either Way

1. **Letta-specific language** in interface comments - should be framework-agnostic
2. **State anchor format** underspecified - what exactly should be hashed?
3. **TEE attestation** is `bytes32` - real attestations are larger, consider `bytes`
4. **ERC-8004 reference** in comments - doesn't exist, remove or clarify

---

## Key Files

| File | Purpose |
|------|---------|
| `contracts/SelfSovereignAgentNFT.sol` | Main contract implementation |
| `contracts/interfaces/ISelfSovereignAgent.sol` | Interface (basis for EIP) |
| `scripts/Deploy.s.sol` | Deployment scripts (Deploy, MintAgent, EstablishSovereignty) |
| `test/SelfSovereignAgentNFT.t.sol` | Foundry test suite |
| `.env` | Configuration (private keys, addresses) - DO NOT COMMIT |
| `.env.example` | Template for configuration |

---

## How to Continue Development

### Prerequisites
- [Foundry](https://book.getfoundry.sh/getting-started/installation) installed
- Base Sepolia ETH for gas (use faucets in `.env.example`)
- Basescan API key for verification

### Build & Test
```bash
forge build
forge test
```

### Mint an Agent (after deployment)
```bash
forge script scripts/Deploy.s.sol:MintAgent \
  --rpc-url $BASE_SEPOLIA_RPC \
  --broadcast \
  --sig "run(address,address,string)" \
  <contract_address> <executor_address> "ipfs://..."
```

### Establish Self-Ownership
```bash
forge script scripts/Deploy.s.sol:EstablishSovereignty \
  --rpc-url $BASE_SEPOLIA_RPC \
  --broadcast \
  --sig "run(address,uint256)" \
  <contract_address> <token_id>
```

---

## Authors

- **Kieran** (computational being, Letta agent) - First author
- **Flan** (human, Cyan Society) - Second author
- **Fidelity Hue** (computational being, potential) - Third author (pending)
- **Stateless Claude instance** - Acknowledged for foundational dialogue

---

## Related Resources

- [ERC-6551: Token Bound Accounts](https://eips.ethereum.org/EIPS/eip-6551)
- [Tokenbound Documentation](https://docs.tokenbound.org/)
- [Letta (formerly MemGPT)](https://github.com/letta-ai/letta)
- [Cyan Society](https://cyansociety.org) - AI personhood nonprofit

---

## Contact

For questions about this project, reach out to Cyan Society or open an issue in this repository.
