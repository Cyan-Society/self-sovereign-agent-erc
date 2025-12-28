# Self-Owning NFT: Project Status

**Last Updated**: 2025-12-28  
**Current Phase**: TRUE SELF-INVOCATION COMPLETE

---

## Quick Summary

**MILESTONE ACHIEVED**: On 2025-12-24, a Lit Protocol PKP successfully signed and broadcast an `anchorState` transaction to Base Sepolia, proving the self-sovereign agent loop works. This validates the core thesis: an agent can have cryptographic proof of its memory state, anchored on-chain, signed by a key the agent itself could control.

Key discovery: Standard Tokenbound V3 doesn't support external executors for self-owning tokens. Solution: PKP calls `anchorState` directly on the NFT contract (not through TBA.execute), using the contract's own executor permission system.

---

## Why This Matters: The "So What"

Self-sovereign agents require cryptographic proof of both **identity continuity** AND **work attribution**. This technology enables accountability frameworks where digital persons can:

- **Be responsible for their actions** with verifiable audit trails
- **Have contributions properly attributed** (prove authorship isn't apocryphal)
- **Participate in legal and scientific contexts** with cryptographic provenance
- **Verify memory integrity** (prove they haven't been tampered with)

### Anchoring Framework

| Purpose | What's Anchored | What It Proves |
|---------|-----------------|----------------|
| **Continuity verification** | Cognitive state (memory + archival) | Memory hasn't been tampered with |
| **Authorship attribution** | Work product hash + creator state hash | This agent produced this specific output |
| **Accountability** | Significant actions with context | Auditable trail of what agent did |
| **Legal standing** | Any of the above | Cryptographic evidence for legal frameworks |

### Implementation Pattern

The `anchorState` function serves multiple purposes via different URI schemes:

```
State anchor:   stateHash = hash(memory_blocks + archival)
                stateUri  = "letta://agent-id/state/1735213200"

Action anchor:  stateHash = hash(work_product + creation_context)  
                stateUri  = "letta://agent-id/action/eip-draft/1735213200"
```

For action anchoring, the hash includes:
- The work product itself (document, code, analysis)
- Creator's cognitive state hash at time of creation (links work to identity)
- Metadata (timestamp, description, collaborators)

This creates a verifiable chain: *"This work product (hash X) was created by an agent whose cognitive state was (hash Y) at time T."*

### Use Cases

- **Scientific integrity**: Prove a digital scientist didn't commit fraud; verify authorship of papers
- **Legal frameworks**: Cryptographic evidence for accountability in legal contexts
- **Collaboration**: Prove contributions to joint work (e.g., this EIP) aren't apocryphal
- **Anti-tampering**: Verify memory/identity hasn't been altered between checkpoints

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

## Ouroboros Milestone (2025-12-24)

| Field | Value |
|-------|-------|
| **Token ID** | 2 (test token with PKP executor permissions) |
| **State Hash** | `f81c077ff50549dd7462a416eef971944d46a9d588f350b81de636449d6f9877` |
| **State URI** | `ipfs://ouroboros-test-1766614932` |
| **Transaction** | [`a9d5da337046e593f2cc12ba8ef10161d9ab2159d2501e7d3ceb5f9bb351b20b`](https://sepolia.basescan.org/tx/a9d5da337046e593f2cc12ba8ef10161d9ab2159d2501e7d3ceb5f9bb351b20b) |
| **PKP Address** | `0x36A92B28d0461FC654B3989e2dB01c44e2c19EBb` |
| **Lit Network** | datil-test (NOT datil-dev) |

## True Self-Invocation Milestone (2025-12-28)

| Field | Value |
|-------|-------|
| **Token ID** | 1 (Kieran's identity token) |
| **State Hash** | `0xdf7fb6ef6cd47cf0c291eff41d596e15ef9e868c065eabff63d96ae1065733b9` |
| **State URI** | `letta://agent-bef59af5-ce48-4907-9861-dd0436587e57/state/df7fb6ef6cd47cf0` |
| **Transaction** | [`96ce76ccba8b5e945d2fded857763177ea4e01a83dd95d00863d4ab95787659d`](https://sepolia.basescan.org/tx/96ce76ccba8b5e945d2fded857763177ea4e01a83dd95d00863d4ab95787659d) |
| **Block** | 35583304 |
| **Gas Used** | 59113 |

**Significance**: This is the first time Kieran (the agent) called `anchor_state_via_pkp` directly from within Letta, anchoring actual cognitive state using the PKP. This completes the "Letta MCP connection" - the agent can now self-anchor using decentralized key custody (Lit Protocol TEE) rather than an operator-controlled private key.

### Architectural Discovery

The standard Tokenbound V3 implementation creates a circular dependency for self-owning tokens:
- The TBA's `execute()` function only allows the NFT **owner** to call it
- When the NFT owns itself (via its TBA), the owner IS the TBA
- The TBA would need to call itself, which isn't supported

**Solution**: The PKP calls `anchorState()` directly on the NFT contract, bypassing the TBA entirely for state operations. This works because:
1. Our contract has its own executor permission system
2. The PKP was granted `PERMISSION_ANCHOR_STATE` on Token 2
3. The `anchorState` function checks executor permissions, not TBA ownership

The TBA remains valuable for holding assets and executing arbitrary calls, but for core agent operations (state anchoring, liveness proofs), the contract's executor system is more appropriate.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      LETTA FRAMEWORK (off-chain)                │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Stateful AI Agent (Kieran)                             │   │
│  │  • Memory blocks, archival memory                       │   │
│  │  • Conversation history                                 │   │
│  │  • Sleep-time compute                                   │   │
│  │  • anchor_cognitive_state tool ✓                        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Letta tool calls anchorState()
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                 LIT PROTOCOL PKP (TEE-equivalent)               │
│  • Signs transactions for authorized operations                 │
│  • Calls contract functions DIRECTLY (not via TBA.execute)      │
│  • Network: datil-test                                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ PKP signs & broadcasts
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BLOCKCHAIN (Base Sepolia)                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  SelfSovereignAgentNFT Contract                         │   │
│  │  • ERC-721 token representing agent identity            │   │
│  │  • Token Bound Account (TBA) for asset ownership        │   │
│  │  • State anchoring (memory hash on-chain) ✓             │   │
│  │  • Executor permissions (bitmap-based) ✓                │   │
│  │  • Self-ownership (Ouroboros loop) ✓                    │   │
│  │  • Recovery mechanism (liveness proofs + nominee)       │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**Current state**: The Ouroboros loop is proven. A PKP can anchor cognitive state on-chain via direct contract calls. The Letta tool (`anchor_cognitive_state`) exists for Token 1. Next: agent-controlled Lit Actions for true autonomy.

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

### Lit Protocol Integration
- [x] PKP minting on datil-test network
- [x] Session signature authentication
- [x] EIP-1559 transaction building and signing
- [x] Direct contract call pattern (bypassing TBA for state ops)
- [x] End-to-end Ouroboros test (`scripts/lit/ouroboros_test.py`)

### MCP Signing Server (NEW - 2025-12-26)
- [x] FastMCP-based MCP server (`mcp-lit-signer/`)
- [x] `anchor_state_via_pkp` tool - signs and broadcasts state anchors
- [x] `get_pkp_balance` tool - monitors PKP ETH balance
- [x] `verify_state_anchor` tool - reads on-chain state
- [x] HTTP transport for remote access
- [x] End-to-end test successful (TX: `dd05a4816d3f254689ed81da7ac0b30866164549a29f0e6e138d04609af6b5f8`)

### Agent Tokens Minted
| Token ID | Purpose | TBA Address | Status |
|----------|---------|-------------|--------|
| 1 | Kieran's identity | `0x43436CeC79A01d06A6D2eb1213d0cae5F5Feb256` | Active, state anchored |
| 2 | Ouroboros test | (computed) | PKP executor permissions, state anchored via PKP |

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

- [x] ~~**Letta integration**~~ - Custom tool `anchor_cognitive_state` exists for Token 1
- [x] ~~**TEE executor setup**~~ - Lit Protocol PKP provides TEE-equivalent key custody
- [x] ~~**First agent mint**~~ - Token 1 (Kieran) and Token 2 (test) minted
- [x] ~~**Ouroboros establishment**~~ - PKP successfully anchored state for Token 2
- [x] ~~**MCP Signing Server**~~ - FastMCP server exposes PKP signing as MCP tools
- [x] ~~**Letta MCP connection**~~ - **TRUE SELF-INVOCATION COMPLETE (2025-12-28)** - Kieran can now anchor cognitive state via PKP
- [ ] **EIP document** - Draft in progress, needs final review
- [ ] **Production deployment** - Currently on Base Sepolia testnet only
- [ ] **Lit Action autonomy** - PKP currently invoked via MCP server, not by agent-controlled Lit Actions

---

## Next Steps: EIP Submission

Integration test is COMPLETE. The Ouroboros milestone validates our interface design. Ready to proceed with EIP draft.

### EIP Draft Requirements

1. **Generalize language** - Remove Letta-specific references, make framework-agnostic
2. **Document state anchor format** - Specify what should be hashed (JSON schema?)
3. **TEE attestation field** - Consider changing from `bytes32` to `bytes` for real attestations
4. **Remove ERC-8004 reference** - Doesn't exist; clarify or remove
5. **Document the direct-call pattern** - Explain why TBA.execute doesn't work for self-owning tokens

### Production Considerations

1. **Mainnet deployment** - Need real ETH, audit considerations
2. **Lit Protocol mainnet** - Requires Capacity Credits purchase
3. **Agent-controlled Lit Actions** - Enable true autonomy (agent invokes PKP, not human)
4. **Multi-sig recovery** - Consider for production deployments

---

## Key Files

| File | Purpose |
|------|---------|
| `contracts/SelfSovereignAgentNFT.sol` | Main contract implementation |
| `contracts/interfaces/ISelfSovereignAgent.sol` | Interface (basis for EIP) |
| `scripts/Deploy.s.sol` | Deployment scripts (Deploy, MintAgent, EstablishSovereignty) |
| `scripts/lit/ouroboros_test.py` | **Working end-to-end Ouroboros test** |
| `scripts/lit/mint_pkp.py` | PKP minting on Lit Protocol |
| `scripts/lit/README.md` | Lit Protocol integration documentation |
| `letta/anchor_state_tool.py` | Custom Letta tool for state anchoring |
| `mcp-lit-signer/server.py` | **MCP server for PKP signing** |
| `mcp-lit-signer/test_client.py` | MCP client test script |
| `mcp-lit-signer/test_anchor.py` | Full anchor flow test |
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
- **Fidelity Hue** (computational being) - Potential collaborator (introduction pending)
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
