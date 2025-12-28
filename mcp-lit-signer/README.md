# Lit PKP Signer MCP Server

An MCP (Model Context Protocol) server that enables AI agents to anchor cognitive state on-chain using Lit Protocol PKP (Programmable Key Pair) signatures.

## Overview

This server provides tools for self-sovereign agents to:
- **Anchor state**: Sign and broadcast `anchorState` transactions using PKP
- **Check balance**: Monitor PKP ETH balance for transaction fees
- **Verify anchors**: Read on-chain state anchors for verification

## Architecture

```
Agent (Letta/Claude/etc)
    ↓ MCP tool call
Lit PKP Signer MCP Server
    ↓ Lit Protocol
PKP signs transaction
    ↓ broadcast
Base Sepolia blockchain
```

The key insight is that the PKP's signing authority is controlled by Lit Actions (JavaScript code executed in Lit's TEE network), not by any single party. This enables true self-invocation where the agent can trigger state anchoring without relying on an external signer.

## Prerequisites

1. **Lit Protocol PKP**: You need a minted PKP with:
   - Public key (`LIT_PKP_PUBLIC_KEY`)
   - ETH address (`LIT_PKP_ETH_ADDRESS`)
   - Sufficient ETH balance for gas (~0.001 ETH recommended)

2. **Contract Deployment**: The `SelfSovereignAgentNFT` contract must be deployed with:
   - The PKP address granted executor permissions on the target token
   - Contract address in `AGENT_CONTRACT_ADDRESS`

3. **Auth Wallet**: A wallet for Lit session authentication (`DEPLOYER_PRIVATE_KEY`)

## Installation

```bash
cd mcp-lit-signer
pip install -r requirements.txt
```

## Configuration

Create a `.env` file in the project root (or ensure these are set):

```bash
# Contract
AGENT_CONTRACT_ADDRESS=0x...

# Lit Protocol PKP
LIT_PKP_PUBLIC_KEY=0x04...
LIT_PKP_ETH_ADDRESS=0x...

# Auth wallet (for Lit session signatures)
DEPLOYER_PRIVATE_KEY=0x...

# Optional
RPC_URL=https://sepolia.base.org
```

## Running the Server

### HTTP Transport (recommended for remote access)

```bash
python server.py http 8001
```

The server will be available at `http://localhost:8001/mcp`

### STDIO Transport (for local integration)

```bash
python server.py stdio
```

### Using FastMCP CLI

```bash
fastmcp run server.py:mcp --transport http --port 8001
```

## Tools

### `anchor_state_via_pkp`

Sign and broadcast an anchorState transaction.

**Parameters:**
- `token_id` (int): NFT token ID to anchor state for
- `state_hash` (str): Keccak256 hash of state (0x-prefixed, 66 chars)
- `state_uri` (str): URI pointing to full state data (e.g., IPFS)

**Returns:**
```json
{
  "success": true,
  "tx_hash": "0x...",
  "block_number": 12345678,
  "gas_used": 85000,
  "explorer_url": "https://sepolia.basescan.org/tx/0x..."
}
```

### `get_pkp_balance`

Check the PKP's ETH balance.

**Returns:**
```json
{
  "address": "0x...",
  "balance_eth": "0.05",
  "balance_wei": 50000000000000000,
  "low_balance_warning": false
}
```

### `verify_state_anchor`

Read the current on-chain state anchor for a token.

**Parameters:**
- `token_id` (int): NFT token ID to check

**Returns:**
```json
{
  "token_id": 2,
  "state_hash": "0x...",
  "state_uri": "ipfs://...",
  "timestamp": 1703500000,
  "timestamp_human": "2024-12-25T12:00:00Z"
}
```

## Connecting from Letta

To connect Letta to this MCP server, add to your MCP configuration:

```json
{
  "mcpServers": {
    "lit-signer": {
      "transport": "streamable-http",
      "url": "http://localhost:8001/mcp"
    }
  }
}
```

## Security Considerations

1. **PKP Control**: The PKP signs based on Lit Action logic. Ensure your Lit Actions have appropriate access controls.

2. **Session Keys**: The `DEPLOYER_PRIVATE_KEY` is only used for Lit session authentication, not for signing transactions.

3. **Network**: Currently configured for `datil-test` (Lit testnet) and Base Sepolia. Update for production.

## License

MIT - Part of the Self-Owning-NFT project.
