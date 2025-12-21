# **The Mechanics of Token Bound Accounts: An Exhaustive Technical Analysis of ERC-6551 Architectures, Permission Models, and Extension Patterns**

## **1\. Introduction: The Evolution of Non-Fungible Identity**

The Ethereum ecosystem has historically treated Non-Fungible Tokens (NFTs) conforming to the ERC-721 standard as static assets—digital pointers to metadata that reside within the storage of an Externally Owned Account (EOA) or a smart contract. While this model succeeded in establishing digital provenance, it failed to provide NFTs with agency. An NFT could be owned, but it could not own; it could be transferred, but it could not transact. This limitation necessitated the development of ERC-6551, a standard for Token Bound Accounts (TBAs). ERC-6551 fundamentally alters the on-chain object model by assigning a deterministic, fully functional smart contract wallet to every ERC-721 token, thereby transforming static assets into dynamic, self-sovereign identities capable of accumulating on-chain history, holding assets, and interacting with decentralized applications (dApps).1

This report provides a comprehensive deep dive into the mechanics of ERC-6551. It moves beyond high-level abstraction to analyze the specific permission models of the canonical implementation, the advanced executor-aware logic of production environments like Tokenbound V3, and the emerging standard patterns for custom implementations. By dissecting the bytecode-level architecture, the interplay with ERC-4337 Account Abstraction, and the security implications of ownership loops, this analysis offers a definitive technical reference for architects and developers operating at the frontier of NFT composability.

## **2\. The Canonical Architecture: Determinism and State Association**

To understand the advanced permission models utilized in modern TBA implementations, one must first deconstruct the canonical architecture defined in the ERC-6551 proposal. The standard’s primary innovation lies not in the account logic itself, but in the mechanism of binding that account to an NFT in a manner that is permissionless, compatible with existing infrastructure, and deterministic.

### **2.1 The Registry and CREATE2 Determinism**

The architectural cornerstone of ERC-6551 is the Registry—a singleton smart contract deployed to a consistent address across all Ethereum Virtual Machine (EVM) compliant chains. The current canonical Registry address, 0x000000006551c19487814612e58FE06813775758, serves as the immutable entry point for all TBA queries and deployments.3 Unlike previous composability standards like ERC-998, which required wrapping the original NFT or modifying its contract state, the ERC-6551 Registry acts as a "factory of factories," utilizing the CREATE2 opcode to calculate account addresses derived from the NFT’s identity rather than the deployer’s nonce.

The CREATE2 opcode ensures that the address of a smart contract is computed based on the deployer's address, a salt, and the keccak256 hash of the contract's initialization code. In the context of ERC-6551, this determinism is weaponized to decouple asset reception from account deployment. A TBA address can be computed for an NFT that was minted seconds ago, or even for an NFT that has not yet been minted (provided the ID is known). This address can immediately receive ETH, ERC-20 tokens, or other NFTs. The account contract itself needs only to be deployed when the owner decides to execute a transaction to move those assets.4

The uniqueness of a Token Bound Account is defined by a specific tuple of parameters passed to the Registry’s createAccount or account functions:

* implementation: The address of the logic contract (e.g., the canonical Account.sol or a custom V3 implementation).  
* salt: A 32-byte unique value allowing a single NFT to own multiple distinct accounts.  
* chainId: The ID of the blockchain where the NFT resides.  
* tokenContract: The address of the ERC-721 contract.  
* tokenId: The unique identifier of the specific NFT.5

This mechanism creates a 1:N relationship between an NFT and its accounts. While an NFT typically has one "canonical" account (often derived with salt=0), the inclusion of the salt parameter allows for an infinite array of specialized accounts—one for savings, one for gaming inventory, and one for voting rights—all bound to the same root asset.

### **2.2 Bytecode-Level Binding: The ERC-1167 Extension**

A critical engineering challenge in ERC-6551 was providing the account contract with awareness of its own identity without incurring the prohibitive gas costs of storage writes during deployment. If every TBA required initializing storage variables for tokenContract and tokenId, the cost of creating an account would deter adoption.

The solution employed by the canonical implementation is a modification of the ERC-1167 Minimal Proxy standard. Standard ERC-1167 proxies are tiny contracts that simply delegate all calls to an implementation address. ERC-6551 proxies extend this by appending the account's context data directly to the bytecode of the proxy itself. This data is "immutable" in the strictest sense—it is part of the code, not the storage.5

The structure of the deployed bytecode is a precise concatenation of instructions and data:

| Segment | Size | Description |
| :---- | :---- | :---- |
| **ERC-1167 Header** | 10 bytes | Standard EVM instructions to prepare for delegation. |
| **Implementation Address** | 20 bytes | The address of the logic contract (Account.sol). |
| **ERC-1167 Footer** | 15 bytes | Instructions to execute DELEGATECALL and return data. |
| **Salt** | 32 bytes | The differentiator value. |
| **Chain ID** | 32 bytes | The chain where the bound NFT exists. |
| **Token Contract** | 32 bytes | The address of the NFT collection. |
| **Token ID** | 32 bytes | The specific ID of the bound NFT. |

When the implementation contract executes logic (e.g., checking ownership), it does not read from its own storage. Instead, it performs a codecopy operation to retrieve these values from the footer of the proxy's bytecode. This architectural choice has profound implications:

1. **Gas Efficiency:** Deployment cost is minimized because no SSTORE operations occur during the createAccount call.  
2. **Immutability:** The binding between the account and the NFT is cryptographically unbreakable. It is impossible to update the tokenId of a deployed proxy because doing so would require changing the code at that address, which is generally immutable (excluding SELFDESTRUCT scenarios, which are being deprecated).  
3. **Context Awareness:** The implementation logic is generic, but the proxy instance is specific. One implementation contract can serve millions of NFTs, with each proxy supplying its unique context via the footer.7

## **3\. The Canonical Permission Model**

The "canonical" implementation refers to the reference contracts provided in the ERC-6551 repository (often Version 0.2 or the basic Reference implementation). This implementation enforces a strict, owner-centric permission model that treats the NFT holder as the sole authorized controller of the account.

### **3.1 Synchronous Ownership Resolution**

The primary mechanism for authorization in the canonical model is the \_isValidSigner check. Unlike a standard EOA, which authenticates via a private key signature, a TBA authenticates via the state of the Ethereum blockchain.

When the executeCall function is invoked on the TBA, the contract performs the following logic sequence:

1. **Context Retrieval:** It extracts the tokenContract and tokenId from its own bytecode footer.  
2. **External Query:** It performs a static call to IERC721(tokenContract).ownerOf(tokenId).  
3. **Comparison:** It compares the returned address from the external query against the msg.sender (the caller of the function).  
4. **Execution:** If and only if msg.sender matches the NFT owner, the transaction proceeds.

This model is defined as "Synchronous Ownership Resolution." The right to execute is determined at the exact moment of execution based on the current state of the NFT contract.5

**Implications of Synchronous Resolution:**

* **Instant Transfer:** If the NFT is transferred from Alice to Bob, Alice immediately loses access to the TBA, and Bob immediately gains access. There is no "update" transaction required on the TBA itself.  
* **Dependency Risk:** The TBA is entirely dependent on the availability and correct behavior of the NFT contract. If the NFT contract is paused, upgraded to a malicious implementation, or simply reverts on ownerOf, the TBA becomes permanently frozen. This highlights that the security model of a TBA is the intersection of the ERC-6551 implementation and the underlying NFT contract.8

### **3.2 The executeCall Interface**

The canonical implementation exposes a specific function signature for execution:  
executeCall(address to, uint256 value, bytes calldata data)  
This function is intentionally named executeCall rather than the generic execute to avoid function selector collisions with other standards during the early development phase of the EIP. It allows the NFT owner to trigger any low-level operation: transferring ERC-20 tokens, interacting with DeFi protocols, or minting other NFTs. The function strictly verifies ownership and then triggers a low-level call op-code. Crucially, the canonical implementation tracks a state variable (nonce) that increments with every execution, providing a mechanism for off-chain indexers to track account activity ordering.5

### **3.3 Signature Validation (ERC-1271)**

A robust smart contract wallet must do more than execute transactions; it must be able to sign messages. This is handled via ERC-1271 compatibility. The canonical TBA implements the isValidSignature function, which allows dApps to verify if a specific signature acts as a valid authorization for the TBA.

The logic mirrors the execution model:

1. The dApp provides a hash and a signature to the TBA.  
2. The TBA determines the current owner of the NFT.  
3. The TBA checks if the provided signature is valid for that owner.

This enables **Recursive Ownership**. If an NFT is owned by a multisig wallet (e.g., Gnosis Safe), the TBA can be controlled by that multisig. When the TBA is asked to validate a signature, it delegates the check to the multisig. If the multisig validates the signature (according to its threshold logic), the TBA returns the "magic value" confirming validity. This chain of trust allows for arbitrarily deep nesting of asset ownership.4

## **4\. Executor-Aware Architectures: Tokenbound V3 Mechanics**

While the canonical implementation provides a secure baseline, it lacks flexibility. Specifically, it rigidly couples "holding the NFT" with "executing transactions." In many advanced use cases—such as on-chain gaming or automated portfolio management—it is desirable to delegate execution rights to a third party (an "Executor") without transferring the underlying NFT. To address this, the Tokenbound team introduced the V3 implementation, which features an "Executor-Aware" permission model.

### **4.1 The AccountGuardian: A Trusted Registry**

Tokenbound V3 introduces a separate infrastructure component known as the AccountGuardian. This contract serves as a centralized (or governance-controlled) registry that manages security policies for TBAs. The AccountGuardian maintains two critical datasets:

1. **Trusted Implementations:** A list of Account.sol logic contracts that are verified to be secure.  
2. **Trusted Executors:** A list of addresses authorized to perform specific actions on TBAs, typically used for cross-chain bridging or system-wide administrative tasks.10

The AccountGuardian interface includes functions like setTrustedExecutor(address executor, bool trusted) and setTrustedImplementation(address implementation, bool trusted). By referencing this guardian, a V3 account can determine if a caller is a system-recognized entity, adding a layer of managed security on top of the trustless code.11

### **4.2 Decoupled Permissions: The execute Logic**

In the V3 Account.sol, the execution logic is significantly more sophisticated than the canonical executeCall. The function is renamed to execute to align with broader smart account standards (like ERC-4337 and ERC-6900).

The V3 permission check evaluates multiple conditions to authorize a caller:

1. **Owner Access:** Is msg.sender the current holder of the NFT? (Standard canonical behavior).  
2. **Guardian Access:** Is msg.sender listed as a Trusted Executor in the AccountGuardian?  
3. **Local Permissions:** Has the account locally stored a permission granting execution rights to msg.sender?

This third condition is the most transformative. It allows the NFT owner to call a function (e.g., grantPermission) to whitelist a secondary address (like a hot wallet or a game server) to execute transactions. This enables **Session Keys**: a user can grant a game client the right to sign transactions for 24 hours. The user keeps the NFT in their cold storage Ledger, while the hot wallet executes gameplay transactions. If the hot wallet is compromised, the user simply revokes the permission on-chain without losing the asset.10

### **4.3 ERC-4337 Integration and validateUserOp**

The most significant mechanical leap in executor-aware TBAs is the native integration of ERC-4337 (Account Abstraction). This allows TBAs to operate as "UserOperations" in an alternative mempool, enabling gas abstraction (Paymasters) and batched transactions.

For a contract to be 4337-compliant, it must implement the validateUserOp function. The EntryPoint contract calls this function to verify if the account authorizes a proposed operation.

The V3 validateUserOp Implementation Mechanics:  
The function signature is validateUserOp(PackedUserOperation calldata userOp, bytes32 userOpHash, uint256 missingAccountFunds). The implementation within Tokenbound V3 performs the following rigorous checks:

1. **Caller Verification:** The function asserts require(msg.sender \== entryPoint()). This ensures that only the canonical EntryPoint contract can trigger validation, preventing replay attacks or unauthorized state changes.11  
2. **Signer Recovery:** The signature field from the userOp is extracted.  
3. **Hybrid Authorization Check:** The contract uses \_isValidSigner(recoveredSigner) to validate the signature. Crucially, this check leverages SignatureChecker.isValidSignatureNow (from OpenZeppelin) to support both EOA signatures (ECDSA) and Smart Contract signatures (EIP-1271). This is vital because the "Owner" of the NFT might be a DAO or a Multisig. If the signature belongs to the NFT owner *or* an authorized executor, the validation passes.4  
4. **Nonce Management:** The account explicitly increments its nonce to prevent the reuse of old signatures.  
5. **Gas Payment:** If the missingAccountFunds parameter is greater than zero (meaning a Paymaster is not covering the full cost), the TBA executes a transfer of ETH back to the EntryPoint to pay for its own gas. This closes the loop on the "NFT as a Wallet" concept—the NFT itself pays for its transaction fees using the ETH stored within it.11

The distinction between execute (direct call) and validateUserOp (4337 call) is critical. execute relies on msg.sender (the caller pays gas), while validateUserOp relies on cryptographic signatures (the account or paymaster pays gas). Tokenbound V3 supports both, creating a "Dual-Interface" account.

## **5\. Standard Patterns for Custom Extensions**

The ERC-6551 standard is deliberately minimal ("unopinionated"), mandating only the interface and the deployment pattern. This has led to a Cambrian explosion of custom implementations. Analyzing the ecosystem reveals three dominant design patterns for extending the reference.

### **5.1 The Inheritance Extension Pattern**

The most common pattern for custom TBAs is inheritance. Developers import the canonical ERC6551Account.sol and override specific virtual functions to inject business logic. This is safer than forking the code as it maintains interface compliance.

**Key Use Cases & Mechanics:**

* **Whitelisting/Blacklisting:** Developers override the execute function to inspect the to (target) address before calling super.execute().  
  Solidity  
  function execute(address to, uint256 value, bytes calldata data, uint256 op) public payable override returns (bytes memory) {  
      require(isWhitelisted(to), "Target not allowed");  
      return super.execute(to, value, data, op);  
  }

  This pattern is ubiquitous in "Game Accounts" where the developer wants to ensure the TBA can only interact with the game's official contracts, preventing players from accidentally draining assets or trading on unauthorized markets.14  
* **Locking Mechanisms:** To use an NFT as collateral in DeFi without transferring it to a vault, custom implementations add a lock(uint256 until) function. The execute function is overridden to revert if block.timestamp \< lockTimestamp. This allows the user to prove they cannot move the assets for a set time, enabling "non-custodial staking" where the NFT stays in the user's wallet but its contents are frozen.10

### **5.2 The Modular Account Pattern (Modules)**

Influenced by ERC-6900 and ERC-7579, advanced TBA implementations are adopting a modular architecture. Instead of hardcoding logic into the Account.sol, the implementation includes a fallback function or a module manager that delegates execution to external contracts.

In this pattern, the TBA storage contains a mapping of enabledModules. The execute function checks if the caller is an enabled module. This allows a TBA to "install" new capabilities—such as a "Recurring Payment Module" or a "Social Recovery Module"—without upgrading the core implementation code. This is becoming the standard for long-lived identity NFTs (like ENS names or Lens Profiles), as it allows the account to evolve over time.15

### **5.3 Handling Non-Canonical Ownership (ERC-1155)**

The reference implementation assumes ownerOf(tokenId) returns a single address. ERC-1155 tokens, however, are semi-fungible; a single Token ID can be held by thousands of users simultaneously. The canonical model breaks here because ownerOf does not exist on ERC-1155.

Custom implementations for ERC-1155s utilize the **Salt-Based Differentiation Pattern**. Since the salt is part of the account's address derivation, the salt is used to encode the specific owner's address.

* **Derivation:** salt \= keccak256(abi.encode(ownerAddress, uniqueSalt))  
* **Validation:** The account implementation stores the intended owner in its state (initialized at deployment) or validates that the caller holds at least *one* unit of the ERC-1155 token.

However, a more robust pattern involves overriding owner() to return address(0) and implementing a custom isValidSigner that checks IERC1155(token).balanceOf(user, id) \> threshold. This effectively turns the TBA into a "Collective Account" owned by the group of token holders, often requiring governance or multisig-like logic to execute transactions.16

## **6\. Cross-Chain Mechanics and Synchronization**

A fundamental limitation of the canonical architecture is locality: an NFT on Ethereum Mainnet generates a TBA address on Mainnet, but that same address can also be generated on Polygon. How does the Mainnet NFT control the Polygon TBA?

### **6.1 Unified Deployment Factory ("Nick's Factory")**

The Registry is deployed using a "Presigned Transaction" submitted to a specific deployment factory known as "Nick's Factory" (deployed at 0x4e59b44847b379578588920cA78FbF26c0B4956C on all chains). Because the deployer address (the factory), the nonce, and the initialization code of the Registry are identical on every EVM chain, the Registry address 0x00...6551... is universal.4

Consequently, the computed TBA address Create2(Registry, salt, code) is also universal (assuming the implementation contract is also deployed at a consistent address). This means a user effectively owns the "same" account address on Optimism, Arbitrum, and Base, derived from their Mainnet NFT.

### **6.2 Reactive State Synchronization**

For the Mainnet NFT to actually *control* the Polygon TBA, the system relies on **Cross-Chain Message Passing (CCMP)**. Custom implementations, such as the "Cross-Chain ERC-6551" proposal, introduce a reactive layer:

1. **Origin Chain:** When the NFT is transferred, a "Connector" contract emits an event or sends a message via a bridge (LayerZero/CCIP).  
2. **Destination Chain:** A ReactiveRegistry receives the message containing the new owner's address.  
3. **Local Update:** The Polygon TBA updates its local storage to recognize the new Mainnet owner as the valid signer.

Without this reactive layer, the Polygon TBA remains strictly bound to the *local* ownership of a nonexistent (or bridged) representation of the NFT on Polygon. This area is currently the subject of active R\&D, with developers building "Mirror" NFTs on L2s solely to act as local control keys for L2 TBAs.17

## **7\. Security Implications and Threat Models**

The power of TBAs introduces specific threat vectors that differ from standard wallets.

### **7.1 The Marketplace Front-Running Attack**

The most critical security risk involves the atomicity of trading an NFT and its bound assets.  
Scenario:

1. Alice lists a "Level 50 Wizard" NFT (whose TBA holds 1000 GOLD tokens) on OpenSea.  
2. Bob purchases the NFT.  
3. Alice observes the pending purchase transaction.  
4. Alice front-runs Bob by submitting a execute(transfer 1000 GOLD) transaction on the TBA with a higher gas fee.  
5. Alice's transfer executes first; the TBA is emptied.  
6. Bob's purchase executes; he receives the empty Wizard.

**Mitigation:** This cannot be solved by the TBA contract alone. It requires **Marketplace Awareness**. Marketplaces must check the nonce or lastTransactionTimestamp of the TBA. If the state of the TBA changes in the same block as the sale, the sale should revert. Alternatively, users must use "Locking Extensions" (Section 5.1) to cryptographically freeze the TBA contents while the NFT is listed.14

### **7.2 Ownership Cycles (The "Black Hole")**

It is possible to transfer NFT A into the TBA of NFT B, and then transfer NFT B into the TBA of NFT A. This creates a circular dependency where neither account has an accessible EOA owner. The assets inside both accounts become permanently irretrievable—a "Black Hole."

The canonical implementation does not prevent this because traversing the ownership graph to detect loops is prohibitively expensive (gas-wise) on-chain. Protection against this relies on client-side safety checks in wallets and interfaces (e.g., Tokenbound.org SDK throws a warning if the destination is a known TBA).14

## **8\. Conclusion**

ERC-6551 represents a paradigm shift from "User-Centric" to "Token-Centric" identity. The canonical implementation provides the necessary cryptographic primitives—CREATE2 determinism and bytecode context injection—to essentially "retrofit" every existing NFT with a wallet. However, the ecosystem is rapidly converging on the **Executor-Aware V3** architecture. This model, by integrating ERC-4337 validateUserOp and AccountGuardian permissions, successfully decouples the rigid asset ownership of ERC-721 from the dynamic execution needs of modern dApps.

For developers extending this standard, the path forward is clear: adopt the V3-style separation of concerns. Use the proxy for identity, the implementation for logic, and the Guardian for security. As the "Reactive" cross-chain patterns mature, TBAs will likely become the primary vessel for digital inventory, allowing users to carry a unified, portable identity across the fragmented landscape of Layer 2 networks.

### **Data Appendix: Comparison of Implementation Versions**

| Feature | Canonical (V2/Ref) | Tokenbound V3 (Executor-Aware) |
| :---- | :---- | :---- |
| **Primary Entry Point** | executeCall | execute |
| **Permission Check** | Strict msg.sender \== ownerOf | msg.sender is Owner OR Authorized Executor |
| **ERC-4337 Support** | No (requires wrapper) | Native (validateUserOp) |
| **Initialization** | Context in Bytecode | Context in Bytecode \+ initialize (Multicall) |
| **Trust Model** | Trustless (Immutable code) | Managed (Guardian controls upgrades/executors) |
| **SDK Method** | execute (polyfilled) | execute (native) |

This technical foundation allows ERC-6551 to serve as the bedrock for the next generation of "Playable" and "Executable" NFTs.

#### **Works cited**

1. Ethereum NFT Standards: ERC-721, ERC-1155, ERC-6551, and More, accessed December 19, 2025, [https://rya-sge.github.io/access-denied/2025/01/14/ethereum-nft-standard/](https://rya-sge.github.io/access-denied/2025/01/14/ethereum-nft-standard/)  
2. Understanding ERC-6551: Token Bound Accounts \- LearnWeb3, accessed December 19, 2025, [https://learnweb3.io/lessons/understanding-erc-6551-token-bound-accounts/suggest/](https://learnweb3.io/lessons/understanding-erc-6551-token-bound-accounts/suggest/)  
3. erc6551/reference: ERC-6551 reference implementation \- GitHub, accessed December 19, 2025, [https://github.com/erc6551/reference](https://github.com/erc6551/reference)  
4. ERC-6551 Standard: Token Bound Accounts (TBA) | By RareSkills, accessed December 19, 2025, [https://rareskills.io/post/erc-6551](https://rareskills.io/post/erc-6551)  
5. A Complete Guide to ERC-6551: Token Bound Accounts, accessed December 19, 2025, [https://goldrush.dev/guides/a-complete-guide-to-erc-6551-token-bound-accounts/](https://goldrush.dev/guides/a-complete-guide-to-erc-6551-token-bound-accounts/)  
6. How to Create and Deploy a Token Bound Account (ERC-6551), accessed December 19, 2025, [https://www.quicknode.com/guides/ethereum-development/nfts/how-to-create-and-deploy-an-erc-6551-nft](https://www.quicknode.com/guides/ethereum-development/nfts/how-to-create-and-deploy-an-erc-6551-nft)  
7. ERCs/ERCS/erc-6551.md at master · ethereum/ERCs \- GitHub, accessed December 19, 2025, [https://github.com/ethereum/ERCs/blob/master/ERCS/erc-6551.md](https://github.com/ethereum/ERCs/blob/master/ERCS/erc-6551.md)  
8. ERC-6551: Non-fungible Token Bound Accounts \- Page 6, accessed December 19, 2025, [https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=6](https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=6)  
9. Understanding ERC-6551: Token Bound Accounts \- LearnWeb3, accessed December 19, 2025, [https://learnweb3.io/lessons/understanding-erc-6551-token-bound-accounts/](https://learnweb3.io/lessons/understanding-erc-6551-token-bound-accounts/)  
10. tokenbound/contracts: Opinionated ERC-6551 account ... \- GitHub, accessed December 19, 2025, [https://github.com/tokenbound/contracts](https://github.com/tokenbound/contracts)  
11. Address: 0x2326aa72...be27aa952 | Etherscan, accessed December 19, 2025, [https://etherscan.io/address/0x2326aa72fb2227f7c685fe9bc870ddfbe27aa952](https://etherscan.io/address/0x2326aa72fb2227f7c685fe9bc870ddfbe27aa952)  
12. ERC 4337: account abstraction without Ethereum protocol changes, accessed December 19, 2025, [https://medium.com/infinitism/erc-4337-account-abstraction-without-ethereum-protocol-changes-d75c9d94dc4a](https://medium.com/infinitism/erc-4337-account-abstraction-without-ethereum-protocol-changes-d75c9d94dc4a)  
13. The EntryPoint Contract \- ERC-4337 Documentation, accessed December 19, 2025, [https://docs.erc4337.io/smart-accounts/entrypoint-explainer.html](https://docs.erc4337.io/smart-accounts/entrypoint-explainer.html)  
14. ERC-6551: Non-fungible Token Bound Accounts \- Page 2, accessed December 19, 2025, [https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=2](https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=2)  
15. ERC-7656: Variation to ERC6551 to deploy any kind of contract ..., accessed December 19, 2025, [https://ethereum-magicians.org/t/erc-7656-variation-to-erc6551-to-deploy-any-kind-of-contract-linked-to-any-contract-included-nfts/19223](https://ethereum-magicians.org/t/erc-7656-variation-to-erc6551-to-deploy-any-kind-of-contract-linked-to-any-contract-included-nfts/19223)  
16. ERC-6551: Non-fungible Token Bound Accounts \- Page 4, accessed December 19, 2025, [https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=4](https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=4)  
17. Cross-Chain ERC-6551 \- Reactive Network, accessed December 19, 2025, [https://blog.reactive.network/cross-chain-erc-6551/](https://blog.reactive.network/cross-chain-erc-6551/)