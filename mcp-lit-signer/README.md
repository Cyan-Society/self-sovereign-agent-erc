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

# MCP transport authentication (required)
MCP_API_KEY=<generate-a-random-bearer-token>

# Optional
RPC_URL=https://sepolia.base.org
MCP_HOST=127.0.0.1
```

Generate the MCP bearer token with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Do not pass this token as a tool argument. HTTP clients send it in the
`Authorization: Bearer <token>` header. The server fails to start if
`MCP_API_KEY` is absent. Configuration is loaded from `.env` beside `server.py`
first (flat deployments), then from the parent directory (repository layout).
A process manager may instead inject the variables directly, for example with
a systemd `EnvironmentFile=` directive.

This static shared token is a transitional protection for the current local
signer, not client identity or production-grade authorization. It has no
per-client identity, expiry, or independent policy decision. Replace it with
the Phase 2 identity-bound broker before treating signer calls as attributable
to a particular agent.

## Running the Server

### HTTP Transport

```bash
python server.py http 8001
```

The server defaults to `127.0.0.1` and will be available at
`http://localhost:8001/mcp`. Keep it on loopback unless an authenticated TLS
proxy or an equivalent explicitly reviewed network boundary fronts it.

Non-loopback operation is not recommended with this static verifier. During a
controlled migration only, `MCP_HOST` can override the bind address, but bearer
authentication, TLS, and source-network firewall restrictions are all required.
Plain HTTP exposes bearer credentials to anyone able to observe the network
path, so do not use it across an untrusted network. Replace this mode rather
than promoting it to a production signer boundary.

### STDIO Transport (for local integration)

```bash
python server.py stdio
```

`MCP_API_KEY` is still required at startup so configuration fails closed, but
HTTP bearer middleware does not authenticate STDIO. Use STDIO only where the
parent process and local pipe boundary are already trusted.

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
      "url": "http://localhost:8001/mcp",
      "headers": {
        "Authorization": "Bearer ${MCP_API_KEY}"
      }
    }
  }
}
```

The exact environment-variable interpolation syntax is client-specific. Verify
that your client resolves the token from its secret/environment store rather
than persisting the literal credential in tracked configuration or transcripts.

## Security Considerations

1. **Transport authentication**: Every HTTP MCP request, including discovery and read-only tools, requires the configured bearer token. Network filtering is defense in depth, not a substitute for authentication.

2. **Binding**: The safe default is loopback. The static verifier is transitional and must not be treated as production or identity-bound authorization. Any temporary non-loopback migration requires an explicit `MCP_HOST`, TLS, and source-network restrictions.

3. **PKP control**: The PKP signs based on Lit Action logic. The current action must not be treated as an identity-bound production policy until destination, method, token, rate, and caller authorization are constrained and tested.

4. **Session keys**: The `DEPLOYER_PRIVATE_KEY` is used for Lit session authentication. Although it is not the PKP transaction key, compromise can grant meaningful signing-session authority; protect and rotate it accordingly.

5. **Network and chain**: The current code targets `datil-test` and Base Sepolia. It is testnet software, not a production signer boundary.

## License

MIT - Part of the Self-Owning-NFT project.
