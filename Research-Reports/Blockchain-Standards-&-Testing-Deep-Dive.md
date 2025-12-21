# **Technical Architecture and Implementation Strategies for Autonomous On-Chain Agents: A Deep Dive into ERC-6551, ERC-8004, and TEE Verification**

## **1\. Introduction: The Agentic Stack**

The Ethereum ecosystem is currently undergoing a fundamental architectural shift, transitioning from a user-centric interaction model—where human users initiate every transaction via externally owned accounts (EOAs)—to an agent-centric model where autonomous software entities execute complex, multi-step workflows. This transition requires a robust infrastructure stack capable of conferring the same properties we expect for human users—asset ownership, persistent identity, reputation, and operational verification—onto software agents. The following report provides an exhaustive technical analysis of the three critical primitives enabling this shift as of late 2025: ERC-6551 (Token Bound Accounts), ERC-8004 (Trustless Agent Identity), and On-Chain Trusted Execution Environment (TEE) Verification.

The synergy of these technologies addresses the "Trust Gap" in decentralized AI. While smart contracts provide deterministic execution for on-chain logic, they cannot natively verify the integrity of off-chain computation (such as LLM inference or complex arbitrage logic). Conversely, off-chain agents lack persistent on-chain identity and asset-holding capabilities. ERC-6551 bridges the asset gap by binding smart contract wallets to NFTs. ERC-8004 creates a standardized registry for discovery and reputation. Finally, TEE attestation (specifically via the DCAP protocol) provides the cryptographic link between the off-chain silicon executing the agent's logic and its on-chain identity. This report dissects the mechanics, implementation patterns, and testing strategies for this emerging stack.

## ---

**2\. ERC-6551 Deep Dive: Mechanics, Permissions, and Execution**

The ERC-6551 standard, titled "Non-fungible Token Bound Accounts," represents a significant evolution in digital asset utility. Unlike previous attempts at NFT composability (such as ERC-998), which required complex modifications to the token standards themselves, ERC-6551 achieves composability through a permissionless registry system that acts as a factory for smart contract accounts.1 This separation of concerns allows any existing ERC-721 token to retroactively acquire a smart wallet without upgrading the original NFT contract.

### **2.1 The Canonical Registry and Proxy Mechanics**

The heart of the ERC-6551 infrastructure is the singleton Registry contract. It is deployed at the vanity address 0x000000006551c19487814612e58FE06813775758 across all Ethereum Virtual Machine (EVM) compatible chains.1 This consistency is achieved through a standardized keyless deployment transaction, ensuring that an NFT on Mainnet and its bridged equivalent on Optimism can theoretically derive the same account address if the implementation logic is consistent.

#### **The CREATE2 Determinism and Bytecode Structure**

The Registry employs the create2 opcode to compute account addresses deterministically. This capability is vital because it allows the ecosystem to "know" the address of an NFT's account before that account is explicitly deployed—a property known as counterfactual addressing.2 The address derivation relies on a specific formula:

$$AccountAddress \= keccak256(0xff \++ RegistryAddress \++ Salt \++ keccak256(InitCode))$$  
The Salt in the context of ERC-6551 is a composite value derived from the chainId, tokenContract address, and tokenId, alongside an optional user-defined salt value. This user-defined salt enables a single NFT to control multiple distinct accounts (e.g., a "Savings" account and a "Trading" account).3

To optimize for gas efficiency, the Registry does not deploy full implementation contracts for every account. Instead, it utilizes a custom ERC-1167 minimal proxy. Standard ERC-1167 proxies are stateless forwarders that delegate all calls to a logic contract. ERC-6551 modifies this pattern by appending **immutable arguments** to the proxy's bytecode. This is a critical architectural decision: rather than storing the NFT's context (Token ID, Contract Address, Chain ID) in contract storage—which would incur expensive SLOAD operations—this data is hardcoded into the deployed bytecode itself.3

The bytecode structure of a Token Bound Account (TBA) is as follows:

1. **ERC-1167 Header (10 bytes):** Standard initialization for delegation.  
2. **Implementation Address (20 bytes):** The address of the logic contract (e.g., AccountV3.sol).  
3. **ERC-1167 Footer (15 bytes):** Instructions to delegate execution.  
4. **Salt (32 bytes):** The unique differentiator.  
5. **Chain ID (32 bytes):** The chain ID where the NFT resides.  
6. **Token Contract (32 bytes):** The address of the NFT collection.  
7. **Token ID (32 bytes):** The specific identifier of the token.

The implementation contract retrieves this context at runtime by using calldatacopy to read the footer of its own code. This mechanism ensures that the account logic always knows "who owns me" without trusting any storage state that could be manipulated.4

### **2.2 The Canonical Permission Model**

The reference implementation of ERC-6551 establishes a permission model that is strictly hierarchical and dynamic. The security of the TBA is entirely derivative of the security of the NFT it is bound to.

#### **The Dynamic owner() Function**

A distinct feature of the canonical implementation is the owner() function. Unlike typical Ownable contracts where ownership is a static address stored in a variable, the ERC-6551 owner() function performs a real-time lookup.

1. The contract extracts the tokenContract, tokenId, and chainId from its own bytecode.  
2. It verifies if the current chain matches the chainId in the bytecode.  
3. It calls IERC721(tokenContract).ownerOf(tokenId) to fetch the current holder of the NFT.1

This design implies that ownership transfer is atomic with the NFT transfer. If Alice transfers the NFT to Bob, Bob immediately becomes the owner() of the TBA and controls all assets within it. There is no separate "handover" transaction required for the account itself. This effectively turns the NFT into a bearer instrument for the underlying liquidity and identity stored in the TBA.

#### **The Basic isValidSigner Logic**

Authorization in the canonical implementation is handled by the isValidSigner(address signer, bytes calldata context) function. Its primary role is to gatekeep the execute function.

* **Logic:** It returns the ERC-1271 magicValue (0x523e3260) if and only if the signer matches the address returned by owner().  
* **Limitation:** In the base implementation, *only* the NFT holder can sign transactions. This creates a friction point for autonomous agents, as the "agent" (the software) would need to hold the NFT itself to execute transactions, or the user would have to sign every action manually.1 This limitation necessitates "Executor-Aware" implementations for agentic workflows.

### **2.3 Executor-Aware TBA Implementations (Tokenbound V3)**

To enable autonomous agents to operate a TBA without the user surrendering custody of the NFT, developers must utilize an **Executor-Aware** implementation. The industry standard for this is the **Tokenbound V3** suite, specifically AccountV3.sol and its associated AccountGuardian.

#### **Architecture of AccountV3**

Tokenbound V3 extends the canonical model by introducing a dual-layer permission system. It retains the root ownership of the NFT holder but adds a mechanism to delegate execution rights to other addresses (executors). This allows an AI agent's signing key to trigger transactions on the TBA while the NFT remains safely in the user's cold storage.5

The AccountV3 contract typically includes:

1. **ERC-1271 Signature Validation:** Allows the TBA to sign messages (e.g., "Login with Ethereum") validatable by other dApps.  
2. **Multicall Support:** Enabling batching of transactions for gas efficiency.  
3. **Nested Execution:** Logic to handle chains of ownership (e.g., TBA A owns NFT B, which has TBA B).  
4. **Granular Permissions:** The critical feature for agents.

#### **The AccountGuardian and Security**

The AccountGuardian contract in the V3 architecture serves as an immutable registry of security policies. It allows users to define "trusted implementations" and manage upgradeability. A key function of the Guardian is to prevent malicious upgrades that could lock assets or change ownership logic unexpectedly.5 It acts as a safety anchor, often enforcing a timelock or specific governance constraints on critical account changes.

#### **The Executor Permission Pattern**

In AccountV3.sol, the execute function's authorization check (\_isValidSigner) is expanded beyond simple ownership. The logic flows as follows:

Solidity

function \_isValidSigner(address signer, bytes calldata context) internal view returns (bool) {  
    // 1\. Check if signer is the direct owner of the NFT  
    if (signer \== owner()) return true;

    // 2\. Check if the owner has explicitly granted permission to this signer  
    if (permissions\[owner()\]\[signer\]) return true;

    // 3\. (Optional) Check context-specific permissions  
    return false;  
}

This implies a standard setup pattern for AI Agents:

1. **Initialization:** The User (holding the NFT) calls a function like setPermissions(AgentAddress, true) on the TBA.  
2. **Operation:** The Agent (running in a TEE) generates a transaction and signs it with AgentAddress.  
3. **Execution:** The Agent submits the transaction to the TBA's execute function. The TBA verifies AgentAddress is a valid signer and executes the call.2

This decoupling is vital. It allows the Agent to be a "hot wallet" with limited funds or scope, while the "Identity" (the NFT) remains secure. If the Agent behaves maliciously or is compromised, the User simply revokes the permission on-chain.

### **2.4 Standard Patterns for Custom Extensions**

Developers extending the reference implementation must adhere to specific patterns to maintain composability with the broader ERC-6551 ecosystem (marketplaces, explorers, indexers).

#### **Pattern 1: Storage Layout Compatibility**

Because the Registry deploys proxies that use delegatecall, the storage layout of the implementation contract is paramount. If a custom implementation introduces new state variables, they must be appended *after* the storage variables defined in the base TokenboundAccount contract. Failing to do so will result in storage collisions, corrupting critical data like \_state (nonce) or permission mappings.1

#### **Pattern 2: Context-Aware isValidSigner**

The isValidSigner function includes a bytes calldata context parameter which is often unused in simple implementations. However, for robust agentic systems, this parameter is the standard vector for implementing **Session Keys** or **Scoped Permissions**.

* **Usage:** The context bytes can decode into a struct containing { validUntil, allowedSelectors, maxValue }.  
* **Logic:** The \_isValidSigner function decodes this context and verifies that the current transaction adheres to these constraints. This allows a user to grant an agent permission to "Only trade on Uniswap" or "Only execute for the next 100 blocks".8

#### **Pattern 3: The "Cycle" Prevention**

A nuance of TBAs is the potential for ownership cycles (e.g., Account A owns NFT B, Account B owns NFT A). This locks assets permanently. Standard implementations often include a check in execute preventing the transfer of the bound NFT to the account's own address. However, identifying indirect cycles is computationally expensive on-chain. Best practice for custom implementations is to implement onERC721Received hooks that reject the receipt of the underlying token itself, preventing the most immediate form of "black hole".9

## ---

**3\. ERC-8004: The Trustless Agent Identity Standard**

While ERC-6551 provides the "wallet" and "container" for an agent, it does not solve the problems of discovery, reputation, or non-financial trust. ERC-8004, titled "Trustless Agents," is the emerging standard designed to address these layers. It provides a standardized mechanism for agents to register their capabilities and for users (or other agents) to verify their reliability without centralized intermediaries.

### **3.1 Current Status and Evolution (Dec 2025\)**

Status: Draft.  
ERC-8004 was officially proposed in August 2025.10 As of December 2025, it remains in the Draft stage of the Ethereum Improvement Proposal (EIP) process. It is not yet finalized. The standard is being actively iterated upon by a coalition including the Ethereum Foundation's dAI team, MetaMask, Consensys, and Phala Network.11  
**Key Changes and Refinements (Aug \- Dec 2025):**

* **Mandatory AgentCard:** Initial drafts treated the off-chain metadata (the "Agent Card") as optional. Recent updates have made exposing this Agent Card at a well-known URI mandatory to ensure consistent discoverability.12  
* **Singleton Registry Architecture:** To prevent fragmentation where agents exist on disparate registries, the community has converged on a Singleton pattern per chain for the Identity Registry, mirroring the success of the ERC-6551 Registry.12  
* **Decoupling of Payments:** Early discussions considered embedding payment logic (like micropayment channels) directly into the standard. The consensus has shifted to keeping ERC-8004 strictly focused on *trust* (Identity, Reputation, Validation) and delegating payment mechanics to complementary standards like **x402** (a protocol for payments over HTTP/Streams).12

### **3.2 The Tripartite Registry Architecture**

ERC-8004 defines a system of three interoperable registries. These contracts are lightweight, intended to store pointers and hashes rather than large datasets.

#### **1\. Identity Registry (IIdentityRegistry)**

This is the root directory. It issues a unique AgentID (minted as an ERC-721 token) to every registered agent. This makes the agent's identity itself a transferable, composable asset.10

Interface Mechanics:  
The core function is registerAgent. It links an EVM address (the controller) to an off-chain URI.

Solidity

interface IIdentityRegistry {  
    // Registers a new agent.   
    // @param agentAddress: The address controlling the agent (e.g. the TBA).  
    // @param agentURI: IPFS link to the Agent Card JSON.  
    function registerAgent(address agentAddress, string calldata agentURI) external returns (uint256 agentID);  
      
    // Resolution functions  
    function getAgent(uint256 agentID) external view returns (address agentAddress, string memory agentURI);  
    function resolveAgentId(address agentAddress) external view returns (uint256 agentID);  
}

**The Agent Card:** The agentURI points to a JSON file containing the agent's name, description, endpoints (where to send tasks), and supported trust models.14

#### **2\. Reputation Registry (IReputationRegistry)**

This registry allows agents to build a verifiable track record. To prevent Sybil attacks and spam, the standard enforces a **Pre-Authorization** model.

* **Mechanism:** An agent cannot simply "rate" another agent. The Service Provider (Agent A) must sign a message authorizing the Client (Agent B) to leave feedback for a specific task.  
* **Data Structure:** The registry stores a numeric score (0-100), optional semantic tags (e.g., latency, accuracy), and a URI pointing to detailed evidence.13

**Interface Mechanics:**

Solidity

interface IReputationRegistry {  
    function submitFeedback(  
        uint256 targetAgentID,  
        uint8 score,  
        bytes32 calldata tags,  
        string calldata evidenceURI,  
        bytes calldata authorizationSignature // Prevents unauthorized spam  
    ) external;  
}

#### **3\. Validation Registry (IValidationRegistry)**

This registry is the critical link for TEE integration. It records proofs that a specific task was executed correctly.

* **Trust Models:** It supports multiple verification types:  
  * **Optimistic:** Validators stake tokens and can be slashed if they falsely validate.  
  * **Cryptographic:** TEE Attestation (Intel SGX/TDX quotes) or ZK-Proofs.  
* **Flow:** An agent requests validation for a taskID. A validator submits a validationResponse (Pass/Fail) along with the proof data.10

### **3.3 Reference Implementations and Alignment**

For developers building today, relying on the raw EIP text is insufficient due to its flux. Two primary reference implementations have emerged as the de facto standards:

1. **Phala Network (erc-8004-tee-agent):**  
   * **Focus:** This is the most complete implementation for TEE-based agents.  
   * **Extensions:** It extends the ValidationRegistry specifically to handle **TEE Attestations**. It includes logic to parse Intel DCAP quotes and verify them against an on-chain root of trust.  
   * **Deployment:** Live contracts exist on Base Sepolia (IdentityRegistry at 0x8506...).15  
   * **Recommendation:** Align with this implementation if your agent runs inside a TEE (SGX/TDX), as it provides the necessary hooks for hardware verification.  
2. **dStack:**  
   * **Focus:** Infrastructure and SDKs.  
   * **Features:** Provides tooling to automatically generate the "Agent Card" JSON and handle the signing of reputation authorizations. It simplifies the off-chain interactions required to interface with the on-chain registries.15

## ---

**4\. TEE Attestation On-Chain: Mechanics and Verification**

For an agent to be "Trustless," it must prove "Liveness" and "Integrity"—that it is running the correct code on secure hardware. This is achieved via Trusted Execution Environments (TEEs) and Remote Attestation.

### **4.1 The Attestation Primitive: Intel DCAP**

The industry standard for TEE attestation is Intel's **Data Center Attestation Primitives (DCAP)**. This protocol replaces the older EPID (Enhanced Privacy ID) system. Unlike EPID, which required contacting Intel's centralized servers to verify every quote, DCAP allows for **local** or **on-chain** verification using a chain of ECDSA certificates.16

#### **The Quote Structure**

The DCAP "Quote" is a binary data structure generated by the hardware. Understanding its components is vital for on-chain verification:

1. **Header:** Contains versioning info (V3 for SGX, V5 for TDX/SGX unified).  
2. **ISV Enclave Report (Local Report):**  
   * MRENCLAVE: A cryptographic hash of the code running inside the enclave. This is the **identity of the software**.  
   * MRSIGNER: The hash of the enclave author's signing key.  
   * ReportData: A 64-byte custom field. **This is the binding link.** The agent generates an Ethereum keypair inside the enclave and places keccak256(PublicKey) into this field. This binds the hardware attestation to the Ethereum account used for signing transactions.17  
3. **Authentication Data:** Contains the ECDSA signature of the Quote, signed by the Quoting Enclave (QE), and the certificate chain (PCK Cert $\\to$ Platform CA $\\to$ Root CA) proving the QE is genuine Intel hardware.

#### **V3 vs. V5 Quotes**

* **V3:** Historically used for Intel SGX.  
* **V5:** The modern standard (adopted late 2024/2025). It unifies SGX and **Intel TDX** (Trust Domain Extensions). TDX is critical for AI agents because it allows entire virtual machines (containing Docker containers and Python stacks) to run in the TEE, whereas SGX was limited to small memory enclaves. Phala and Automata have largely migrated to V5 to support "Confidential VMs".17

### **4.2 Phala Network: Decentralized Verification**

Phala operates as a decentralized network of TEE workers. Its verification mechanism is a hybrid on-chain/off-chain model.

1. **Registration:** A worker node generates a Quote.  
2. **On-Chain Registry:** Phala's TEERegistry contract stores the Intel Root CA public key.  
3. **Verification:** The contract receives the Quote, verifies the certificate chain up to the Root CA, and checks the **TCB Info** (Trusted Computing Base) to ensure the hardware is not vulnerable to known exploits.  
4. **Binding:** If valid, the registry maps the worker's ReportData (its public key) to the MRENCLAVE (the code hash), establishing an on-chain root of trust for that agent.15

### **4.3 Automata Network & The Gas Problem (ZK Verification)**

Verifying a full DCAP Quote (which includes a chain of X.509 certificates) in Solidity is computationally prohibitive, costing approximately 4 million gas per verification. This makes frequent liveness proofs economically impossible on mainnet.

**Automata Network** has solved this via **Proof of Verification**.

1. **Off-Chain Computation:** Instead of the EVM verifying the quote, a **zkVM** (like **RiscZero** or **SP1**) verifies the DCAP quote off-chain.  
2. **ZK-Proof Generation:** The zkVM generates a succinct **Groth16 SNARK proof** attesting that "I have verified the Quote is valid and corresponds to Key X."  
3. **On-Chain Verification:** The Solidity contract (AutomataDcapV3Attestation.sol) verifies this tiny SNARK proof.  
4. **Cost Reduction:** This reduces the gas cost from \~4,000,000 to \~300,000–500,000 gas, making "Trustless Agents" economically viable.17

### **4.4 Oracle Solutions and Contract Integration**

Developers should not attempt to write raw DCAP verifiers in Solidity due to the complexity of X.509 parsing and TCB management. Instead, integrate with existing oracle solutions:

* **Automata DCAP Attestation:** Use the AutomataDcapV3Attestation.sol contract as an oracle. It provides the verifyQuote function or the ZK-optimized verification path.  
* **Phala Verifier:** Use the deployed Verifier contract on Base Sepolia (0x481ce...) which acts as a public good for verifying generic TEE quotes.15

## ---

**5\. Foundry Testing Patterns for Agentic Protocols**

Developing this stack requires testing interactions between Proxies (6551), Registries (8004), and Hardware verifiers (TEEs). Standard unit tests are insufficient; developers must employ **Fork Testing** and **Mocking** patterns.

### **5.1 Environment Setup: Forking is Mandatory**

Since the ERC-6551 Registry and TEE Verifiers are complex singleton contracts with pre-existing state (like Intel Root Keys), deploying them from scratch in every test is impractical. Foundry's forking capability is essential.

**foundry.toml Configuration:**

Ini, TOML

\[profile.default\]  
src \= "src"  
out \= "out"  
libs \= \["lib"\]  
fs\_permissions \= \[{ access \= "read", path \= "./" }\]

\[rpc\_endpoints\]  
base\_sepolia \= "${BASE\_SEPOLIA\_RPC\_URL}"

**Test Setup (test/AgentTest.t.sol):**

Solidity

contract AgentTest is Test {  
    // Canonical Addresses (e.g., Base Sepolia)  
    address constant REGISTRY\_6551 \= 0x000000006551c19487814612e58FE06813775758;  
    address constant PHALA\_VERIFIER \= 0x481ce1a6EEC3016d1E61725B1527D73Df1c393a5;  
      
    function setUp() public {  
        // Create and select a fork  
        uint256 baseFork \= vm.createFork("base\_sepolia");  
        vm.selectFork(baseFork);  
    }  
}

### **5.2 Mocking TEE Attestation**

It is impossible to generate a valid Intel SGX/TDX quote inside a Foundry test environment (as the test runner is not a TEE). Therefore, the **Validation Registry** or **Verifier** must be mocked using vm.mockCall.

Pattern: Mocking the Verifier  
Instead of passing a real massive byte array (the quote), pass a dummy value and force the verifier to return success.

Solidity

import {IVerifier} from "src/interfaces/IVerifier.sol";

function test\_RegisterAgentWithMockedAttestation() public {  
    bytes memory dummyQuote \= hex"deadbeef";  
      
    // Mock the call to verifyAttestation on the Phala Verifier  
    // We tell Foundry: "If this address receives this specific call, return true"  
    vm.mockCall(  
        PHALA\_VERIFIER,  
        abi.encodeWithSelector(IVerifier.verifyAttestation.selector, dummyQuote),  
        abi.encode(true) // Return success  
    );

    // Call the agent contract that internally calls the Verifier  
    myAgentContract.register(dummyQuote);  
      
    // Assert the state changed as expected  
    assertTrue(myAgentContract.isRegistered());  
}

This pattern isolates the agent's registration logic from the complexities of the cryptographic verification.20

### **5.3 Testing ERC-6551 Interactions**

Testing TBAs requires handling the asynchronous nature of execute and the proxy address prediction.

1\. Computing the Address:  
Always compute the address before interaction to ensure your assumptions about the salt and implementation are correct.

Solidity

address predictedTBA \= registry.account(implementation, chainId, tokenContract, tokenId, salt);

2\. Pranking the Executor:  
To test the execute function, you must simulate being the NFT owner or the authorized agent.

Solidity

// Mint NFT to Alice  
nft.mint(alice, tokenId);

// Simulate Alice calling the TBA  
vm.startPrank(alice);  
IERC6551Executable(predictedTBA).execute(targetAddress, value, callData, 0); // 0 \= Call  
vm.stopPrank();

3\. Testing Nested Execution:  
If NFT A is owned by TBA B, executing a transaction on TBA A requires a nested call. This is a complex but necessary test case for agentic composability.

Solidity

// TBA B (owned by Bob) owns NFT A  
nftA.transferFrom(alice, address(tbaB), tokenIdA);

// Bob wants to make TBA A do something.  
// He must call TBA B \-\> which calls TBA A \-\> which performs the Action.  
vm.startPrank(bob);  
bytes memory innerCall \= abi.encodeWithSelector(  
    IERC6551Executable.execute.selector,   
    finalTarget,   
    val,   
    finalData,   
    0  
);  
IERC6551Executable(tbaB).execute(address(tbaA), 0, innerCall, 0);  
vm.stopPrank();

## ---

**6\. Strategic Synthesis: The Future of Autonomous Agents**

The integration of these three standards creates a robust lifecycle for autonomous agents:

1. **Assets (ERC-6551):** The user holds an NFT. This NFT owns a Token Bound Account (TBA), which acts as the agent's treasury and persistent identity.  
2. **Compute (TEE/DCAP):** The Agent software runs in a Phala TEE. It generates a DCAP Quote binding its code hash to an Ethereum keypair.  
3. **Identity (ERC-8004):** The Agent registers this Quote on-chain. The Validation Registry confirms the TEE is secure.  
4. **Authorization (Permissions):** The User sees the validated Agent in the Registry. They call setPermissions on their TBA to whitelist the Agent's key.  
5. **Action:** The Agent can now autonomously trade, arbitrage, or interact with DeFi protocols using the TBA, proving its "liveness" and "integrity" via the TEE, while the User retains ultimate sovereignty via the NFT.

Conclusion:  
While ERC-6551 is fully production-ready, ERC-8004 is currently the moving piece in the stack. Developers should treat its interfaces as mutable and rely on the Phala/Automata reference implementations for stability. The cost barrier of on-chain verification is being solved by ZK-coprocessors (Automata), unlocking the economic viability of this stack on Ethereum Mainnet. This architecture effectively decouples the "Soul" (User/NFT) from the "Brain" (TEE Agent), creating a safe, verifiable, and non-custodial model for the AI agent economy.

### **Key Data Summary Table**

| Component | Standard | Current Status (Dec 2025\) | Critical Function/Struct | Reference Implementation |
| :---- | :---- | :---- | :---- | :---- |
| **Account** | ERC-6551 | Final / V3.1 | isValidSigner | tokenbound/contracts |
| **Identity** | ERC-8004 | Draft | registerAgent | Phala-Network/erc-8004-tee-agent |
| **Attestation** | Intel DCAP | V3 / V5 | V3Quote (Struct) | automata-network/automata-dcap-attestation |
| **Verification** | Hybrid | On-Chain / ZK-SNARK | verifyAttestation | AutomataDcapV3Attestation.sol |

#### **Works cited**

1. How to Create and Deploy a Token Bound Account (ERC-6551), accessed December 19, 2025, [https://www.quicknode.com/guides/ethereum-development/nfts/how-to-create-and-deploy-an-erc-6551-nft](https://www.quicknode.com/guides/ethereum-development/nfts/how-to-create-and-deploy-an-erc-6551-nft)  
2. ERC-6551 Standard: Token Bound Accounts (TBA) | By RareSkills, accessed December 19, 2025, [https://rareskills.io/post/erc-6551](https://rareskills.io/post/erc-6551)  
3. A Complete Guide to ERC-6551: Token Bound Accounts, accessed December 19, 2025, [https://goldrush.dev/guides/a-complete-guide-to-erc-6551-token-bound-accounts/](https://goldrush.dev/guides/a-complete-guide-to-erc-6551-token-bound-accounts/)  
4. ERCs/ERCS/erc-6551.md at master · ethereum/ERCs \- GitHub, accessed December 19, 2025, [https://github.com/ethereum/ERCs/blob/master/ERCS/erc-6551.md](https://github.com/ethereum/ERCs/blob/master/ERCS/erc-6551.md)  
5. tokenbound/contracts: Opinionated ERC-6551 account ... \- GitHub, accessed December 19, 2025, [https://github.com/tokenbound/contracts](https://github.com/tokenbound/contracts)  
6. SDK Reference \- Tokenbound Documentation \- Docs, accessed December 19, 2025, [https://docs.tokenbound.org/sdk/methods](https://docs.tokenbound.org/sdk/methods)  
7. Splitooor | ETHGlobal, accessed December 19, 2025, [https://ethglobal.com/showcase/splitooor-wx679](https://ethglobal.com/showcase/splitooor-wx679)  
8. ERC-20 | Address: 0x1c43cd66...401814efb | Etherscan, accessed December 19, 2025, [https://etherscan.io/token/0x1c43cd666f22878ee902769fccda61f401814efb?a=0xd7af5ea14fad145b2d9fd57e321d7bf8301980b5](https://etherscan.io/token/0x1c43cd666f22878ee902769fccda61f401814efb?a=0xd7af5ea14fad145b2d9fd57e321d7bf8301980b5)  
9. ERC-6551: Non-fungible Token Bound Accounts \- Page 7, accessed December 19, 2025, [https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=7](https://ethereum-magicians.org/t/erc-6551-non-fungible-token-bound-accounts/13030?page=7)  
10. ERC-8004 Explained: Ethereum's AI Agent Standard Guide 2025, accessed December 19, 2025, [https://learn.backpack.exchange/articles/erc-8004-explained](https://learn.backpack.exchange/articles/erc-8004-explained)  
11. Ethereum aims to power AI's future with new ERC-8004 standard, accessed December 19, 2025, [https://cryptoslate.com/how-erc-8004-will-make-ethereum-the-home-of-decentralized-ai-agents/](https://cryptoslate.com/how-erc-8004-will-make-ethereum-the-home-of-decentralized-ai-agents/)  
12. ERC-8004: Trustless Agents \- Ethereum Magicians, accessed December 19, 2025, [https://ethereum-magicians.org/t/erc-8004-trustless-agents/25098](https://ethereum-magicians.org/t/erc-8004-trustless-agents/25098)  
13. ERC‑8004: Trustless Agents with Reputation, Validation & On‑Chain ..., accessed December 19, 2025, [https://www.buildbear.io/blog/erc-8004](https://www.buildbear.io/blog/erc-8004)  
14. ERC-8004: a practical explainer for trustless agents, accessed December 19, 2025, [https://composable-security.com/blog/erc-8004-a-practical-explainer-for-trustless-agents/](https://composable-security.com/blog/erc-8004-a-practical-explainer-for-trustless-agents/)  
15. Phala-Network/erc-8004-tee-agent \- GitHub, accessed December 19, 2025, [https://github.com/Phala-Network/erc-8004-tee-agent](https://github.com/Phala-Network/erc-8004-tee-agent)  
16. Demystifying remote attestation by taking it on-chain, accessed December 19, 2025, [https://collective.flashbots.net/t/demystifying-remote-attestation-by-taking-it-on-chain/2629](https://collective.flashbots.net/t/demystifying-remote-attestation-by-taking-it-on-chain/2629)  
17. Automata's release of DCAP Attestation v1.1 for agentic systems, accessed December 19, 2025, [https://blog.ata.network/automatas-release-of-dcap-attestation-v1-1-for-agentic-systems-84ae98900370](https://blog.ata.network/automatas-release-of-dcap-attestation-v1-1-for-agentic-systems-84ae98900370)  
18. Verifying \- Phala, accessed December 19, 2025, [https://phalanetwork-1606097b.mintlify.app/phala-cloud/attestation/verifying-attestation](https://phalanetwork-1606097b.mintlify.app/phala-cloud/attestation/verifying-attestation)  
19. automata-network/automata-dcap-attestation \- GitHub, accessed December 19, 2025, [https://github.com/automata-network/automata-dcap-attestation](https://github.com/automata-network/automata-dcap-attestation)  
20. mockCall \- foundry \- Ethereum Development Framework, accessed December 19, 2025, [https://getfoundry.sh/reference/cheatcodes/mock-call/](https://getfoundry.sh/reference/cheatcodes/mock-call/)