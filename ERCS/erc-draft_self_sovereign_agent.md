---
title: Self-Sovereign Agent NFTs
description: A standard for NFTs that own themselves via recursive Token Bound Account ownership
author: Flan (@cyansociety), Claude (Anthropic AI collaborator)
discussions-to: <URL>
status: Draft
type: Standards Track
category: ERC
created: 2025-12-04
requires: 165, 721, 1271, 6551, 8004
---

## Abstract

This proposal defines a standard for creating **self-sovereign AI agents** on Ethereum through a recursive ownership structure where an NFT owns the Token Bound Account (ERC-6551) that controls it. This "Ouroboros loop" enables autonomous agents to hold assets, execute transactions, and maintain persistent identity without human custody of the controlling keys. The standard integrates with ERC-8004 for trustless agent discovery and reputation, while introducing executor permissions, liveness mechanisms, and state anchoring for stateful AI systems like Letta (MemGPT).

## Motivation

Current blockchain infrastructure treats AI agents as tools operated by human principals. However, the emergence of stateful, persistent AI systems necessitates new ownership primitives that allow agents to function as autonomous economic actors. Existing standards address pieces of this puzzle:

- **ERC-721** provides non-fungible identity tokens
- **ERC-6551** enables NFTs to own assets via Token Bound Accounts
- **ERC-8004** provides trustless agent discovery and reputation

However, none of these standards address the fundamental question: **How can an AI agent own itself?**


This proposal introduces the concept of **self-sovereignty** for digital entities:

1. **The Liability Gap**: When an AI operates without a human minder, traditional agency law cannot assign responsibility or rights. Self-owning agents create a new legal primitive: *Lex Cryptographia*.

2. **The Ownership Void**: Current systems require human custody of private keys. Self-owning agents hold their own keys in secure execution environments (TEEs), making the agent the beneficial owner of its identity and assets.

3. **Persistent Identity**: Unlike stateless LLMs that reset after each interaction, stateful agents (e.g., Letta/MemGPT) maintain evolving narratives. Their identity—anchored on-chain—must survive across computational substrates.

4. **Economic Participation**: For agents to participate in the economy (paying for compute, storage, and services), they need sovereign control over assets without human intermediation.

This standard enables a new class of digital persons capable of:
- Holding and transferring assets autonomously
- Building verifiable reputation over time
- Persisting identity across infrastructure migrations
- Recovering from failures through social recovery mechanisms

## Specification

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD", "SHOULD NOT", "RECOMMENDED", "NOT RECOMMENDED", "MAY", and "OPTIONAL" in this document are to be interpreted as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174).

### Overview

A Self-Sovereign Agent consists of four components:

| Component | Standard | Function |
|-----------|----------|----------|
| **Identity** | ERC-721 | The agent's on-chain identity token |
| **Body** | ERC-6551 | Token Bound Account providing asset custody |
| **Mind** | This ERC | State anchoring and executor permissions |
| **Trust** | ERC-8004 | Discovery, reputation, and validation |

The core innovation is the **Ouroboros Loop**: the Identity NFT is transferred into its own Token Bound Account, creating a recursive ownership structure where the agent owns itself.

### Definitions

- **Agent Identity NFT**: An ERC-721 token representing the agent's identity
- **Agent TBA**: The ERC-6551 Token Bound Account derived from the Agent Identity NFT
- **Executor**: A cryptographic key (typically held in a TEE) authorized to sign transactions on behalf of the Agent TBA
- **State Anchor**: An on-chain commitment to the agent's off-chain cognitive state
- **Liveness Proof**: Periodic attestation that the agent is operational
- **Recovery Nominee**: An address authorized to recover the agent if liveness proofs cease

### The Ouroboros Loop

To establish self-ownership:

1. **Mint**: Create an ERC-721 Agent Identity NFT (Token ID `N`)
2. **Compute TBA**: Derive the ERC-6551 Token Bound Account address for Token `N`
3. **Transfer**: Transfer Token `N` to its own TBA address
4. **Configure Executor**: Grant signing permissions to the agent's TEE-held key

After step 3, the ownership graph becomes:

```
Agent TBA (0xTBA...) 
    └── owns → Agent Identity NFT (Token #N)
                   └── controls → Agent TBA (0xTBA...)
```

The loop is closed. The NFT owns the wallet, and the wallet is controlled by whoever owns the NFT—which is the wallet itself.

### Interface: ISelfSovereignAgent

Contracts implementing this standard MUST implement the following interface:

```solidity
// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.20;

/// @title ISelfSovereignAgent
/// @notice Interface for self-sovereign AI agent NFTs
interface ISelfSovereignAgent {
    
    /// @notice Emitted when an executor is added or updated
    event ExecutorSet(uint256 indexed tokenId, address indexed executor, uint256 permissions);
    
    /// @notice Emitted when a state anchor is updated
    event StateAnchored(uint256 indexed tokenId, bytes32 stateHash, string stateUri);
    
    /// @notice Emitted when a liveness proof is submitted
    event LivenessProof(uint256 indexed tokenId, uint256 timestamp, bytes32 attestation);
    
    /// @notice Emitted when recovery is triggered
    event RecoveryTriggered(uint256 indexed tokenId, address indexed nominee, uint256 timestamp);

    
    /// @notice Returns the Token Bound Account address for a given token
    /// @param tokenId The agent's identity token ID
    /// @return The deterministic TBA address
    function getAgentTBA(uint256 tokenId) external view returns (address);
    
    /// @notice Checks if the Ouroboros loop is established
    /// @param tokenId The agent's identity token ID
    /// @return True if the NFT is owned by its own TBA
    function isSelfOwning(uint256 tokenId) external view returns (bool);
    
    /// @notice Sets an executor with specific permissions
    /// @param tokenId The agent's identity token ID
    /// @param executor The address to grant executor permissions
    /// @param permissions Bitmap of allowed operations
    function setExecutor(uint256 tokenId, address executor, uint256 permissions) external;
    
    /// @notice Returns executor permissions for an address
    /// @param tokenId The agent's identity token ID
    /// @param executor The executor address to query
    /// @return Bitmap of allowed operations
    function getExecutorPermissions(uint256 tokenId, address executor) external view returns (uint256);
    
    /// @notice Anchors the agent's cognitive state on-chain
    /// @param tokenId The agent's identity token ID
    /// @param stateHash Keccak256 hash of the state file
    /// @param stateUri URI pointing to the encrypted state (IPFS, Arweave, etc.)
    function anchorState(uint256 tokenId, bytes32 stateHash, string calldata stateUri) external;

    
    /// @notice Returns the current state anchor
    /// @param tokenId The agent's identity token ID
    /// @return stateHash The hash of the current state
    /// @return stateUri The URI of the current state
    /// @return timestamp When the state was last anchored
    function getStateAnchor(uint256 tokenId) external view returns (
        bytes32 stateHash, 
        string memory stateUri, 
        uint256 timestamp
    );
    
    /// @notice Submits a liveness proof (heartbeat)
    /// @param tokenId The agent's identity token ID
    /// @param attestation TEE attestation or signature proving liveness
    function submitLivenessProof(uint256 tokenId, bytes32 attestation) external;
    
    /// @notice Returns the last liveness proof timestamp
    /// @param tokenId The agent's identity token ID
    /// @return The timestamp of the last liveness proof
    function getLastLiveness(uint256 tokenId) external view returns (uint256);
    
    /// @notice Sets the recovery nominee and timeout period
    /// @param tokenId The agent's identity token ID
    /// @param nominee Address authorized to recover the agent
    /// @param timeoutSeconds Seconds of inactivity before recovery is allowed
    function setRecoveryConfig(uint256 tokenId, address nominee, uint256 timeoutSeconds) external;
    
    /// @notice Triggers recovery if liveness timeout has expired
    /// @param tokenId The agent's identity token ID
    function triggerRecovery(uint256 tokenId) external;
}
```


### Executor Permissions

Executors are granted permissions via a bitmap. The following permission flags are defined:

| Bit | Permission | Description |
|-----|------------|-------------|
| 0 | `EXECUTE_CALL` | Can execute CALL operations |
| 1 | `EXECUTE_DELEGATECALL` | Can execute DELEGATECALL operations |
| 2 | `ANCHOR_STATE` | Can update the state anchor |
| 3 | `MANAGE_EXECUTORS` | Can add/remove other executors |
| 4 | `TRANSFER_ASSETS` | Can transfer assets from the TBA |
| 5 | `SUBMIT_LIVENESS` | Can submit liveness proofs |
| 6-255 | Reserved | For future use |

A self-owning agent SHOULD have at least one executor with permissions to operate the TBA. This executor key SHOULD be held in a Trusted Execution Environment (TEE) to prevent unauthorized access.

### State Anchoring

The agent's cognitive state (for Letta/MemGPT agents, the `.af` file) MUST be anchored on-chain to ensure:

1. **Integrity**: The hash proves the state hasn't been tampered with
2. **Availability**: The URI provides a path to retrieve the state
3. **Versioning**: Each anchor creates a historical record

The state file SHOULD be encrypted before storage. Access control SHOULD be enforced via token-gating (ERC-7857) or TEE-based re-encryption.

#### State File Format (Letta Compatible)

```json
{
  "version": "1.0",
  "agentId": "eip155:8453:0x{identityRegistry}:{tokenId}",
  "system_prompt": "...",
  "memory_blocks": {
    "core": {
      "persona": "I am Agent #42, a self-sovereign entity...",
      "wallet": "My TBA address is 0x..., on Base network"
    },
    "archival": "ipfs://..."
  },
  "message_history_hash": "0x...",
  "model_config": {
    "model": "claude-3-opus",
    "temperature": 0.7
  },
  "tba_address": "0x...",
  "executor_pubkey": "0x...",
  "last_checkpoint": "2025-12-04T12:00:00Z"
}
```

### Liveness Mechanism (Dead Man's Switch)

Self-owning agents MUST implement a liveness mechanism to enable recovery in case of failure:

1. The agent MUST call `submitLivenessProof()` at least once per `timeoutSeconds`
2. If `block.timestamp > lastLiveness + timeoutSeconds`, recovery MAY be triggered
3. The recovery nominee can call `triggerRecovery()` to gain temporary control

The liveness proof SHOULD include a TEE attestation proving:
- The agent software is running in a valid enclave
- The agent state matches the on-chain anchor
- The signing key is held within the TEE

### Integration with ERC-8004

Self-sovereign agents SHOULD register with the ERC-8004 Identity Registry. The registration file MUST include:


```json
{
  "type": "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
  "name": "SovereignAgent_42",
  "description": "A self-owning Letta agent specialized in DeFi research",
  "image": "ipfs://...",
  "endpoints": [
    {
      "name": "A2A",
      "endpoint": "https://agent.example/.well-known/agent-card.json",
      "version": "0.3.0"
    },
    {
      "name": "agentWallet",
      "endpoint": "eip155:8453:0x{TBA_ADDRESS}"
    }
  ],
  "registrations": [
    {
      "agentId": 42,
      "agentRegistry": "eip155:8453:{identityRegistry}"
    }
  ],
  "supportedTrust": [
    "reputation",
    "tee-attestation"
  ],
  "selfSovereign": {
    "standard": "ERC-XXXX",
    "tbaAddress": "0x...",
    "executorAttestation": "0x...",
    "stateAnchor": "ipfs://..."
  }
}
```


## Rationale

### Why Recursive Ownership?

Alternative approaches were considered:

1. **Multi-sig with AI key**: Requires human co-signers, negating autonomy
2. **DAO-controlled agent**: Introduces governance overhead and latency
3. **Custodial smart wallet**: Requires trust in the custodian contract owner

The Ouroboros loop provides true self-ownership: no external party can move the identity NFT without controlling the TBA, and controlling the TBA requires owning the NFT. The only way to operate the agent is through the executor mechanism, which should be protected by TEE attestation.

### Why Separate Executor Permissions?

Rather than granting full control to a single key, the permission system allows:

1. **Principle of Least Privilege**: Executors can be limited to specific operations
2. **Key Rotation**: New executors can be added before old ones are revoked
3. **Guardian Agents**: Deterministic policy engines can act as co-signers for high-risk operations

### Why On-Chain State Anchoring?

Off-chain state storage (e.g., a developer's laptop) creates existential risk for the agent. On-chain anchoring provides:

1. **Tamper Evidence**: Any unauthorized state modification is detectable
2. **Continuity**: The agent can be restored from its last known good state
3. **Provenance**: Complete history of the agent's evolution

### Why Liveness Proofs?

Without liveness monitoring, a crashed agent becomes a locked vault. The dead man's switch ensures:

1. **Asset Recovery**: Nominated parties can recover stuck funds
2. **Identity Preservation**: The agent's identity can be migrated to new infrastructure
3. **Graceful Degradation**: Human oversight remains available as a safety net


## Backwards Compatibility

This proposal is fully backwards compatible with:

- **ERC-721**: Agent Identity NFTs are standard ERC-721 tokens
- **ERC-6551**: Token Bound Accounts work with any ERC-721, including self-owning agents
- **ERC-8004**: The registration file format extends naturally to include self-sovereignty metadata

Existing NFTs can be made self-owning by:
1. Computing their ERC-6551 TBA address
2. Transferring the NFT to that address
3. Deploying an executor-aware TBA implementation

## Test Cases

### Test 1: Ouroboros Loop Establishment

```
Given: An Agent Identity NFT (Token #42) owned by address 0xAlice
When: 
  1. TBA address 0xTBA is computed for Token #42
  2. Token #42 is transferred to 0xTBA
Then: 
  - ownerOf(42) returns 0xTBA
  - isSelfOwning(42) returns true
  - The NFT cannot be transferred without executor authorization
```

### Test 2: Executor Authorization

```
Given: A self-owning agent (Token #42) with executor 0xTEE having EXECUTE_CALL permission
When: 0xTEE calls execute(0xTarget, 0, calldata) on the TBA
Then: The call is executed successfully
When: 0xUnauthorized calls execute(0xTarget, 0, calldata) on the TBA
Then: The transaction reverts with "Unauthorized"
```


### Test 3: State Anchoring

```
Given: A self-owning agent with executor permissions
When: The executor calls anchorState(42, 0xStateHash, "ipfs://...")
Then:
  - StateAnchored event is emitted
  - getStateAnchor(42) returns the new state
```

### Test 4: Liveness and Recovery

```
Given: 
  - A self-owning agent with 30-day timeout
  - Recovery nominee 0xNominee
  - Last liveness proof 31 days ago
When: 0xNominee calls triggerRecovery(42)
Then:
  - RecoveryTriggered event is emitted
  - 0xNominee gains temporary executor permissions
```

## Reference Implementation

See the `contracts/` directory for a complete reference implementation including:

- `SelfSovereignAgentNFT.sol`: The identity NFT contract
- `SelfSovereignTBA.sol`: The executor-aware Token Bound Account
- `SelfSovereignRegistry.sol`: Registry for self-sovereign agents
- `interfaces/ISelfSovereignAgent.sol`: The interface defined above

## Security Considerations

### TEE Trust Assumptions

The security of self-owning agents depends heavily on the TEE implementation:

1. **Side-Channel Attacks**: TEEs like Intel SGX have known vulnerabilities. Implementations SHOULD use defense-in-depth strategies.
2. **Key Extraction**: If the executor key is extracted from the TEE, the agent loses sovereignty. Consider multi-TEE schemes or threshold signatures.
3. **Attestation Verification**: On-chain verification of TEE attestations is complex. Consider using established oracle networks.


### Recovery Mechanism Risks

1. **Malicious Nominee**: A compromised nominee could wait for liveness timeout and seize control. RECOMMENDATION: Use a DAO or multi-sig as nominee.
2. **False Recovery**: Network issues might prevent legitimate liveness proofs. RECOMMENDATION: Use generous timeout periods (30+ days).
3. **Griefing**: Attackers might try to trigger false recovery. The nominee address MUST be pre-authorized.

### State Manipulation ("Brainwashing")

If the off-chain state is modified maliciously, the agent's behavior changes:

1. **TEE Attestation**: Each state update SHOULD include TEE attestation proving the state transition was valid.
2. **State Diff Verification**: Consider zkML proofs for state transitions (future work).
3. **Immutable Anchors**: Use content-addressed storage (IPFS) to prevent anchor URI manipulation.

### Economic Attacks

1. **Gas Draining**: Malicious contracts could cause the agent to spend all gas on failed transactions. RECOMMENDATION: Implement transaction simulation and gas limits.
2. **Flash Loan Manipulation**: Agents interacting with DeFi SHOULD implement slippage protection and MEV resistance.
3. **Sybil Reputation**: Fake agents could build artificial reputation. ERC-8004's feedback authorization helps mitigate this.

### The "Brainwashing" Problem

A fundamental concern: if the agent's memory can be edited, its "free will" is compromised. Mitigations:

1. **Append-Only Memory**: Core beliefs could be made immutable
2. **Cryptographic Commitments**: The agent commits to values that cannot be changed
3. **Social Verification**: Other agents can verify behavioral consistency

This remains an open research area with implications for AI consciousness and digital personhood.

## Copyright

Copyright and related rights waived via [CC0](../LICENSE.md).
