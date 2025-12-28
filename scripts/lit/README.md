# Lit Protocol Integration for Self-Owning NFT

This directory contains scripts for setting up Lit Protocol PKP (Programmable Key Pair)
integration, enabling autonomous transaction signing for the Ouroboros self-ownership loop.

> **🐍 OUROBOROS COMPLETE (2025-12-24)**: Successfully tested end-to-end PKP-signed state anchoring. See `ouroboros_test.py`.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     SELF-SOVEREIGN AGENT STACK                  │
│                                                                 │
│  Letta Server (Mind)                                            │
│       │                                                         │
│       ▼ (API calls via Session Sigs)                            │
│  Lit Protocol PKP (Wallet in TEE)                               │
│       │                                                         │
│       ▼ (Signs transactions)                                    │
│       │                                                         │
│       ├──► SelfSovereignAgentNFT.anchorState() [DIRECT CALL]    │
│       │    (PKP has PERMISSION_ANCHOR_STATE on contract)        │
│       │                                                         │
│       └──► Tokenbound V3 TBA.execute() [FOR ASSET OPERATIONS]   │
│            (PKP whitelisted as executor on TBA)                 │
│                                                                 │
│  Token (Identity) ◄── Self-owning (owned by its own TBA)        │
└─────────────────────────────────────────────────────────────────┘
```

## Key Architectural Discovery

**Standard Tokenbound V3 doesn't support external executors for self-owning tokens.**

The TBA's `execute()` function only allows the NFT **owner** to call it. When the NFT owns itself (via its TBA), this creates a circular dependency - the TBA would need to call itself.

**Solution**: For core agent operations (state anchoring, liveness proofs), the PKP calls functions directly on the NFT contract, using the contract's own executor permission system. The TBA is still used for asset operations (holding ETH/tokens, executing arbitrary calls).

## Current Configuration

| Field | Value |
|-------|-------|
| **Lit Network** | `datil-test` (NOT datil-dev!) |
| **PKP Token ID** | `0xcafa091bd86518c3e88696336768e0f4a4a24dd2e7a3d14c86464ad8cc2e86f8` |
| **PKP Address** | `0x36A92B28d0461FC654B3989e2dB01c44e2c19EBb` |
| **Target Contract** | `0x9fe33F0a1159395FBE93d16D695e7330831C8CfF` (Base Sepolia) |
| **Test Token** | Token ID 2 (PKP has PERMISSION_ANCHOR_STATE) |

## Prerequisites

1. **Node.js 19+** (required for lit-python-sdk background process)
2. **Python 3.10+**
3. **tstLPX tokens** from Chronicle Yellowstone faucet
4. **Base Sepolia ETH** in PKP address for gas

### Get tstLPX Tokens

1. Go to: https://chronicle-yellowstone-faucet.getlit.dev
2. Enter your controller wallet address
3. Verify on: https://yellowstone-explorer.litprotocol.com

## Installation

```bash
# From project root
pip install lit-python-sdk

# Verify installation
python -c "from lit_python_sdk import connect; print('Lit SDK installed!')"
```

## Scripts

### 1. `mint_pkp.py` - Create PKP Identity

Mints a new PKP (Programmable Key Pair) on Datil-Test network.

```bash
python scripts/lit/mint_pkp.py
```

This will output:
- PKP Token ID (NFT on Chronicle Yellowstone)
- PKP Public Key
- PKP ETH Address (the wallet address for signing)

### 2. `lit_action.js` - Signing Policy

JavaScript code that runs in Lit's TEE (Trusted Execution Environment).
Defines WHEN the PKP is allowed to sign transactions.

Current version: Simple (trusts authorized session sig holder)
Future: Can add constraints like "only sign TBA execute() calls"

### 3. `sign_transaction.py` - Transaction Signing Helper

Helper functions for signing transactions using the PKP.

```python
from scripts.lit.sign_transaction import sign_with_pkp

signature = await sign_with_pkp(
    tx_hash="0x...",
    pkp_public_key="0x...",
    session_sigs=session_sigs
)
```

### 4. `whitelist_pkp_on_tba.py` - TBA Executor Setup

Whitelists the PKP address as an authorized executor on the Tokenbound V3 TBA.

```bash
python scripts/lit/whitelist_pkp_on_tba.py --pkp-address 0x...
```

### 5. `test_ouroboros.py` - Integration Test (Deprecated)

Earlier test script. Superseded by `ouroboros_test.py`.

### 6. `ouroboros_test.py` - **Working End-to-End Test** ⭐

The complete Ouroboros flow that successfully anchored state on 2025-12-24:
1. Build an `anchorState` transaction for Token 2
2. Sign it with the PKP via Lit Protocol (datil-test network)
3. Broadcast the signed transaction to Base Sepolia
4. Verify the state was anchored on-chain

```bash
python scripts/lit/ouroboros_test.py
```

This proves that a PKP (which could be controlled by the agent itself via Lit Actions) can anchor cognitive state on-chain.

## Environment Variables

Add to `.env`:

```bash
# Lit Protocol Configuration
LIT_NETWORK=datil-test
LIT_CONTROLLER_PRIVATE_KEY=0x...  # Uses DEPLOYER_PRIVATE_KEY by default

# PKP Information (filled after minting)
LIT_PKP_TOKEN_ID=
LIT_PKP_PUBLIC_KEY=
LIT_PKP_ETH_ADDRESS=
```

## Security Notes

1. **Controller Key**: The wallet that owns the PKP NFT can manage permissions.
   For production, consider using a multisig.

2. **Lit Actions on IPFS**: For production, upload Lit Actions to IPFS and
   reference by CID for immutability.

3. **Capacity Credits**: On mainnet, you'll need to purchase Capacity Credits
   for network usage. Testnet is free with tstLPX.

## Troubleshooting

### "Node.js process failed to start"
Ensure Node.js 19+ is installed: `node --version`

### "Insufficient tstLPX"
Get tokens from the faucet: https://chronicle-yellowstone-faucet.getlit.dev

### "PKP not authorized"
Check that the auth method (EthWallet) is properly configured with SignAnything scope.

### "Owner not found" or PKP errors
**Make sure you're using `datil-test`, NOT `datil-dev`!** The PKP was minted on datil-test.

### "Insufficient funds" on Base Sepolia
The PKP address needs Base Sepolia ETH for gas. Send ~0.01 ETH to the PKP address.

### TBA.execute() fails for self-owning token
This is expected! Use direct contract calls instead. The TBA's execute() only allows the NFT owner to call it, which creates a circular dependency for self-owning tokens.

## Next Steps

1. **Agent-controlled Lit Actions** - Enable the agent to invoke the PKP directly (true autonomy)
2. **Production deployment** - Mainnet requires Capacity Credits purchase
3. **Multi-token support** - Generalize for multiple agent tokens
