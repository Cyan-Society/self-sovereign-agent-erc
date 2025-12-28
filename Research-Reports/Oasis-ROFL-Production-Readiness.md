# **Production Readiness Assessment of Oasis Runtime Off-chain Logic (ROFL) Framework**

## **1\. Introduction: The Convergence of Confidential Compute and Blockchain**

The evolution of decentralized infrastructure has historically been bifurcated into two distinct paradigms: the immutable, transparent, but computationally constrained world of smart contracts, and the performant, opaque, but centralized world of cloud computing. This dichotomy has severely restricted the development of "stateful" decentralized applications—specifically those requiring heavy computation, such as Artificial Intelligence (AI) inference, and those demanding privacy for proprietary strategies, such as automated high-frequency trading. The introduction of the **Runtime Off-chain Logic (ROFL)** framework by the Oasis Network represents a structural attempt to bridge this divide.

As of late 2025, ROFL has transitioned from an experimental architecture into a production-grade infrastructure layer. Its mainnet launch in July 2025 marked a pivotal moment for the Oasis ecosystem, introducing a capability set that allows developers to deploy arbitrary workloads off-chain while maintaining on-chain verifiability through cryptographic proofs generated within Trusted Execution Environments (TEEs).1 This report provides an exhaustive analysis of ROFL's production readiness, specifically examining its architecture, state persistence mechanisms, active deployment landscape, and the operational "gotchas" that define the developer experience in this new paradigm.

The significance of ROFL lies in its ability to invert the traditional blockchain compute model. Rather than executing logic on every node in the network (consensus-constrained execution), ROFL executes logic on specific, attested nodes (off-chain execution) and verifies the *result* on-chain. This distinction is critical for stateful applications, which require persistent data storage and continuous processing loops that would be economically and technically impossible on a standard Ethereum Virtual Machine (EVM) chain.2

The following analysis draws upon technical documentation, architectural decision records (ADRs), GitHub repositories of live applications, and developer reports from the 2024-2025 period to construct a definitive operational picture of the ROFL framework.

## **2\. Architectural Foundations and TEE Evolution**

To assess production readiness, one must first dissect the underlying architecture that supports ROFL. Unlike standard smart contracts, ROFL applications operate as independent runtimes that interact with the blockchain rather than living strictly within it.

### **2.1 The Split-Runtime Model: RONL and ROFL**

The architectural core of this framework is defined by Oasis Decision Record (ADR) 0024, which formalizes the separation of the runtime into two distinct components with separate Trusted Computing Bases (TCBs):

1. **Runtime On-chain Logic (RONL):** This component represents the traditional blockchain layer, such as the Sapphire ParaTime. It is responsible for consensus, ordering transactions, and maintaining the global ledger state. It executes deterministic logic that must be replicated across all validator nodes.4  
2. **Runtime Off-chain Logic (ROFL):** This is the optional, non-deterministic component. It runs as a separate binary process, isolated within its own TEE. Crucially, it does not participate in consensus. Instead, it "hooks" into the node's infrastructure to receive notifications (e.g., new blocks) and submits transactions back to the RONL layer to update state.4

The production implication of this split is profound. A failure in the ROFL component—such as an infinite loop, a memory leak, or a crash—does not halt the blockchain (RONL). The consensus layer continues to produce blocks regardless of the health of the off-chain logic. This decoupling provides a high degree of resilience for the network but shifts the burden of liveness entirely to the application developer. In a production environment, the "heartbeat" of a ROFL app is not guaranteed by the chain's liveness; it must be managed via external monitoring or on-chain "dead man switches".4

### **2.2 The Hardware Transition: From SGX to TDX**

A defining characteristic of ROFL's maturity in 2025 is the transition from reliance on Intel Software Guard Extensions (SGX) to Intel Trust Domain Extensions (TDX). This hardware evolution is the primary enabler for the "stateful" applications that are the focus of this report.

The Limitations of SGX:  
Early iterations of confidential compute on Oasis relied heavily on SGX. While SGX provides robust isolation at the application process level, it imposes severe restrictions on memory usage via the Enclave Page Cache (EPC). Historically, this limit was around 128MB or 256MB. Applications requiring more memory would trigger expensive paging operations, destroying performance. Furthermore, porting applications to SGX often required rewriting them using specific SDKs (like Rust-SGX) to manage the boundary between trusted and untrusted memory.5 This made running heavy stateful applications, such as databases or AI models, practically infeasible in a production setting.  
The Production Unlock with TDX:  
The introduction of TDX support in late 2024 and its mainnet stability in 2025 changed this landscape. TDX operates at the level of the Virtual Machine (VM), isolating the entire guest OS and application stack from the host hypervisor.

* **Memory Capacity:** TDX supports multi-gigabyte private memory spaces, allowing developers to load large AI models (like Llama 3 adapters) or run in-memory databases (like Redis) entirely within the TEE.7  
* **Lift-and-Shift:** Because TDX virtualizes the hardware, developers can deploy standard Docker containers. The "TDX containers ROFL" flavor is now the default for new projects, enabling a developer to wrap a Python script, a Node.js server, or a Rust binary in a Dockerfile and deploy it without rewriting the codebase for a specific TEE SDK.7

For any enterprise looking to deploy stateful applications in 2025, targeting TDX nodes is effectively mandatory. The "lift and shift" capability reduces the engineering overhead from "cryptography researcher" to "backend engineer," significantly lowering the barrier to entry.6

### **2.3 The Remote Attestation Lifecycle**

Trust in ROFL is not assumed; it is cryptographically proven. The production readiness of the system hinges on the **Remote Attestation** flow, which acts as the gatekeeper for all stateful operations.

When a ROFL app initializes, it performs the following sequence:

1. **Measurement:** The hardware measures the binary code, the initial memory state, and the configuration. This produces a cryptographic hash known as MRENCLAVE (in SGX terms) or MRTD (in TDX terms).9  
2. **Quote Generation:** The TEE requests a "Quote" from the Quoting Enclave (QE). This Quote contains the measurements and is signed by the hardware's attestation key, proving that the software is running on genuine Intel hardware.9  
3. **Registry Verification:** The app submits this Quote to the **Sapphire Registry** (an on-chain smart contract). The Registry compares the Quote's measurements against the approved "Policy" defined by the application developer.4  
4. **Key Derivation:** If the Quote is valid, the app is granted a CapabilityTEE. This allows it to derive specific cryptographic keys (e.g., for disk encryption or signing transactions) that are unique to that application and that security version.4

**Production Failure Mode:** A critical "gotcha" in this process is the management of **TCB Recovery** and **Freshness Proofs**. If Intel discovers a vulnerability in a specific CPU batch, they may revoke the TCB level. ROFL apps running on those nodes will suddenly fail attestation, losing access to their storage keys. Developers must monitor the status of the underlying hardware fleet and be prepared to migrate workloads to updated nodes.9

## ---

**3\. State Persistence and Storage Mechanisms**

The user query specifically targets "stateful applications requiring persistent storage." This is the most complex aspect of ROFL development because TEEs are, by nature, designed to be ephemeral secure processors. To support persistence, ROFL employs a sophisticated "Untrusted Local Storage" paradigm that requires careful handling by developers.

### **3.1 The "Untrusted Local Storage" Architecture**

ROFL applications do not persist data directly to the blockchain for their internal state (which would be prohibitively expensive and slow). Instead, they utilize the storage resources of the compute node hosting them.

**The Mechanism:**

* **Sealing:** Before data leaves the TEE, it is "sealed" (encrypted) using a key derived from the TEE's identity. This ensures that the node operator, who controls the physical disk, sees only opaque, encrypted blobs.4  
* **Host-Guest Interface:** The ROFL runtime communicates with the host node via a specialized protocol. The host exposes a key-value store (typically utilizing BadgerDB) to the guest.  
* **Namespace Isolation:** To prevent collisions between the blockchain's consensus state and the ROFL app's private state, the host transparently prefixes all storage keys with rofl..4

The "Local" Limitation:  
The most critical limitation for production architects is that this storage is local to the specific node. If a developer deploys a ROFL app to Node A, the persistent state resides physically on Node A's SSD.

* If *Node A* crashes and restarts, the state is preserved (persistence).  
* If *Node A* is deregistered or suffers a catastrophic hardware failure, **the state is lost permanently**.  
* The Oasis blockchain does **not** replicate this rofl. storage across the network. It is not part of the global consensus state.11

### **3.2 Database Implementation in TEEs**

With the advent of TDX, the options for handling this persistent data have expanded.

Structured Data Persistence:  
Early SGX implementations were limited to simple key-value pairs due to memory constraints. In 2025, TDX-enabled ROFL apps can run embedded database engines inside the TEE.

* **SQLite Pattern:** A common pattern in production apps like WT3 is to run SQLite within the container. The database file itself is stored on the encrypted volume provided by the host. This allows for complex SQL queries over the data while ensuring that the data at rest is always encrypted.12  
* **BadgerDB:** For Go-based ROFL apps, utilizing an embedded BadgerDB instance is common, leveraging the fast key-value lookup speeds for state management.13

Encrypted Volume Mounting:  
For containerized applications (Docker), ROFL provides a mechanism to mount a persistent volume. The framework handles the encryption of this volume transparently using the TEE's sealing keys.

* *Developer Note:* It is critical to ensure that the volume mount points are correctly defined in the manifest.yaml. Misconfiguration here leads to data being written to the ephemeral container layer, which is wiped on restart.14

### **3.3 Strategies for Redundancy and High Availability**

Given the "single point of failure" risk of local storage, production applications must implement application-level redundancy. This is not provided "out of the box" by the protocol but is a required design pattern for stateful apps.

The Replication Pattern:  
To achieve high availability, developers are deploying multiple instances (replicas) of their ROFL app across different nodes.

1. **Replica Set:** Deploy the app to *Node A*, *Node B*, and *Node C*.  
2. **State Synchronization:** The instances must synchronize state. Since they cannot trust the host network, they must establish secure, attested TLS channels between each other (using their TEE identities to authenticate) to replicate data.15  
3. **Consensus:** For strict consistency, apps may implement a lightweight consensus algorithm (like Raft) *inside* the TEE mesh, or use the Sapphire blockchain as a "checkpointing" layer.

Sapphire as an Anchor:  
A robust pattern observed in 2025 is "State Anchoring." The ROFL app periodically hashes its internal state (or creates a Merkle root) and posts this hash to a smart contract on Sapphire. This provides a tamper-proof checkpoint. If the ROFL node is wiped, the app can potentially restore state by pulling a backup from an external source and verifying it against the on-chain anchor hash.2

## ---

**4\. Production Adoption: Case Studies (2024-2025)**

The ecosystem has matured from experimental hackathon projects to funded, operational applications. The following case studies highlight how specific projects are utilizing ROFL's stateful capabilities in production.

### **4.1 Case Study: WT3 (Autonomous Trading Agent)**

**Overview:** WT3 is an autonomous DeFi hedge fund agent. It manages its own treasury, holds its own private keys, executes trades on exchanges like Hyperliquid, and posts updates to social media.1

**Stateful Architecture:**

* **Key Management:** WT3 generates its Ethereum signing keys *inside* the enclave. These keys are never revealed to the developer or the node operator. They are persisted in the encrypted local storage, ensuring the agent retains control of its funds across restarts.12  
* **Persistence Implementation:** The agent maintains a file named conversation\_history.json. This stores the context of its interactions on Twitter/X (posts, replies, sentiment). This file is serialized, encrypted, and written to the mounted volume.  
* **Failure Recovery:** If the container crashes, the initialization script checks for the existence of conversation\_history.json. If found, it decrypts and loads it to restore the agent's "memory." If the specific node hosting WT3 were to be destroyed, this conversation history would be lost, highlighting the current reliance on single-node persistence for some non-critical data.12

**Developer Insight:** WT3 serves as the reference implementation for **Decentralized Key Management**. It proves that an application can hold custody of assets without a human admin having a "backdoor" key.

### **4.2 Case Study: Zeph (Privacy-First AI Companion)**

**Overview:** Zeph is a conversational AI assistant that processes user queries inside a TEE to prevent data scraping and maintain privacy.2

**Stateful Requirements:**

* **Context Windows:** To function as a coherent assistant, Zeph must remember previous turns of the conversation. This requires maintaining a "Context Window" state.  
* **Privacy Mechanism:** Instead of sending chat logs to a central server (like OpenAI), Zeph stores the chat history in the ROFL node's encrypted storage. The AI inference (Llama model) runs inside the TDX container, accessing this history to generate responses.  
* **Production Scale:** Zeph leverages the high memory capacity of TDX nodes to load the LLM weights and context window into RAM, avoiding the latency of disk I/O during the inference pass.18

### **4.3 Case Study: Flashback Labs (Federated Learning)**

**Overview:** Flashback Labs addresses the data privacy bottleneck in training AI models. It allows users to contribute sensitive data (e.g., medical or financial) to a model training process without revealing the raw data.19

**Stateful Architecture:**

* **Transient vs. Persistent:** Unlike WT3, Flashback focuses on *ephemeral* state for the raw data (which is discarded after processing) and *persistent* state for the model weights (gradients).  
* **Aggregation:** The ROFL node aggregates gradient updates from multiple users. This aggregated state is critical and is periodically anchored on-chain to allow for verifiable checkpoints of the model's evolution.

## ---

**5\. Limitations, Gotchas, and Failure Modes**

Despite the production readiness, the developer experience (DevEx) involves navigating several documented pitfalls. These "gotchas" stem from the unique constraints of TEEs and the specific implementation of ROFL.

### **5.1 The "Unencrypted Logs" Security Hole**

The Gotcha: By default, logs generated by a ROFL application (standard output/error) are not encrypted. They are written to the host node's filesystem to assist with debugging.11  
The Risk: A developer accustomed to Web2 debugging might write print(user\_private\_key) or console.log(sensitive\_payload). In a ROFL environment, this immediately leaks the confidential data to the node operator, completely negating the security of the TEE.  
Production Requirement: Production binaries must have all debug printing stripped. Alternatively, developers must implement an internal encrypted logging mechanism where logs are encrypted with a developer-controlled public key before being written to stdout.11

### **5.2 The "Enclave ID" Mismatch Loop**

The Issue: The identity of a ROFL app is tied to its binary hash (MRENCLAVE). Even a single byte change in the code results in a new hash.10  
The Failure Mode: When deploying an update, if the developer updates the binary before updating the policy on the Sapphire Registry, the app will fail to boot. The Registry will reject the attestation from the new binary because it doesn't match the registered policy.  
Troubleshooting: The error message Unknown enclave or 0xe044 often indicates this mismatch. The operational procedure requires a strict order of operations: 1\) Build new image, 2\) Get new Hash, 3\) Update On-Chain Policy, 4\) Deploy new image.10

### **5.3 Marketplace Economics and Rental Expiry**

Pricing: ROFL nodes are rented via a marketplace. The pricing in late 2025 is typically around 5.0 TEST/hour (on testnet) or the equivalent in ROSE on mainnet.21  
The Gotcha: Compute is rented for fixed terms. If a rental term expires and is not auto-renewed, the node operator is incentivized to shut down the container to free up resources.  
Data Loss Risk: While the encrypted storage might persist on the disk if the node operator is benevolent, there is no guarantee. An expired rental can lead to the deletion of the container and its associated volumes. Production apps must implement auto-funding and auto-renewal scripts to prevent service interruption.11

### **5.4 Network Non-Determinism and API Failures**

The Issue: Unlike RONL, ROFL apps can access the internet (HTTPS).  
Failure Mode: If a ROFL app relies on an external API (e.g., Binance for price feeds), it inherits the failure modes of the web.

* **Rate Limiting:** If multiple ROFL apps run on the same node and share an IP address, they may collectively trigger API rate limits, causing "noisy neighbor" failures.  
* **Consensus Sync:** The ROFL app uses a light client to verify the state of the Oasis chain. If the host node falls out of sync with the network, the ROFL app's view of "current time" and "current block" freezes. This can be catastrophic for time-sensitive applications like trading bots.3

### **5.5 Specific Error Codes**

Developers must be familiar with specific TEE error codes documented in the troubleshooting guides:

* aesm: error 30: Indicates a failure in the SGX Architectural Enclave Service Manager, usually due to missing drivers on the host.10  
* 0xb011 / 0xe044: Specific to TDX Quote generation failures, often requiring a kernel update or a restart of the Quote Generation Service (QGS) on the host.10  
* Operation not permitted: Often caused by the host mounting the /dev directory with noexec permissions, preventing the TEE from launching.10

## ---

**6\. Security Threat Modeling**

The security of a ROFL application differs fundamentally from a smart contract. The threat model must account for the physical control the node operator has over the hardware.

### **6.1 Rollback Attacks**

Since the storage is local and managed by the host, a malicious node operator could theoretically perform a "Rollback Attack."

* **Scenario:** The operator takes a snapshot of the encrypted storage at *Time T*. The app updates the state at *Time T+1*. The operator then restores the storage file from *Time T* and restarts the app.  
* **Impact:** The app "forgets" recent transactions or actions.  
* **Mitigation:** ROFL apps must use **Freshness Counters** or **Monotonic Counters** anchored on the Sapphire blockchain. On boot, the app checks the blockchain for the "latest state hash/counter." If the local storage has a lower counter, the app detects the rollback and refuses to operate.3

### **6.2 Side-Channel Attacks**

While TEEs encrypt memory, they are historically vulnerable to side-channel attacks (analyzing power consumption or memory access patterns to infer data).

* **TDX vs. SGX:** TDX mitigates many of the granular side-channel attacks that plagued SGX by isolating the entire VM. However, the TCB of a TDX container is larger (it includes the guest kernel), which theoretically increases the attack surface.7  
* **Defense:** Production apps should employ "constant-time" cryptographic libraries and minimize data-dependent branching in critical code paths.22

## ---

**7\. Conclusion**

As of 2025, the Oasis ROFL framework has achieved production readiness, effectively solving the "Verifiable Compute" problem for Web3. It allows for the deployment of complex, stateful applications—like AI agents and autonomous hedge funds—that were previously impossible on-chain. The transition to Intel TDX has been the decisive factor, removing the memory barriers that hindered early adoption.

However, "readiness" comes with a caveat: **Operational Complexity**. ROFL shifts the responsibility of state management, redundancy, and disaster recovery from the protocol to the developer. The "Trustless AWS" metaphor is accurate, but it is an AWS without a default S3 SLA. Developers must build their own redundancy.

**Final Recommendations for Production Deployment:**

1. **Mandatory TDX:** Do not attempt to run stateful databases on SGX-only nodes; the memory constraints are a production risk.  
2. **Redundancy is King:** Never rely on a single ROFL node. Deploy a minimum of 3 replicas and implement an application-level synchronization protocol.  
3. **Anchor State On-Chain:** Use Sapphire as the immutable source of truth for state hashes to prevent rollback attacks and allow for disaster recovery.  
4. **Audit Logging:** Implement encrypted logging immediately. Assume standard logs are public.

The ROFL framework is robust, actively used, and economically viable, but it demands a sophisticated "Web2 DevOps" mindset applied to Web3 infrastructure to ensure resilience in a hostile environment.

### ---

**Table 1: Technical Comparison of TEE Implementations in ROFL**

| Feature | Intel SGX (Legacy) | Intel TDX (Production Standard 2025\) |
| :---- | :---- | :---- |
| **Isolation Scope** | Application Process | Entire Virtual Machine (VM) |
| **Memory Limit** | Low (EPC \~128MB). Paging destroys performance. | High (Multi-GB). Near-native performance. |
| **Deployment Model** | Requires porting to SGX SDK (Rust/C++). | "Lift & Shift" standard Docker containers. |
| **Stateful Capability** | Poor. Database management is difficult. | Excellent. Can run Redis/SQLite/Postgres. |
| **Attack Surface (TCB)** | Small (Only app code). | Larger (App code \+ Guest Kernel). |
| **Best Use Case** | Key Management, Signing. | AI Inference, Databases, Complex Agents. |

5

#### **Works cited**

1. Oasis Protocol Foundation Launches ROFL Mainnet \- Unchained, accessed December 27, 2025, [https://unchainedcrypto.com/press-release/oasis-protocol-foundation-launches-rofl-mainnet-verifiable-offchain-compute-framework-powering-ai-applications/](https://unchainedcrypto.com/press-release/oasis-protocol-foundation-launches-rofl-mainnet-verifiable-offchain-compute-framework-powering-ai-applications/)  
2. Breaking the Limits: How Oasis Protocol's ROFL Framework Is ..., accessed December 27, 2025, [https://medium.com/@caerlower/breaking-the-limits-how-oasis-protocols-rofl-framework-is-expanding-what-s-possible-in-web3-8f3c8e2ef630](https://medium.com/@caerlower/breaking-the-limits-how-oasis-protocols-rofl-framework-is-expanding-what-s-possible-in-web3-8f3c8e2ef630)  
3. A Deep Technical Dive into Oasis Protocol's Runtime Offchain Logic ..., accessed December 27, 2025, [https://medium.com/@caerlower/inside-rofl-a-deep-technical-dive-into-oasis-protocols-runtime-offchain-logic-framework-330c9c97559e](https://medium.com/@caerlower/inside-rofl-a-deep-technical-dive-into-oasis-protocols-runtime-offchain-logic-framework-330c9c97559e)  
4. ADR 0024: Runtime Off-chain Logic (ROFL) | Oasis Documentation, accessed December 27, 2025, [https://docs.oasis.io/adrs/0024-off-chain-runtime-logic/](https://docs.oasis.io/adrs/0024-off-chain-runtime-logic/)  
5. Ever wonder what happens when you trade strict security limits for ..., accessed December 27, 2025, [https://www.reddit.com/r/oasisnetwork/comments/1nq20od/ever\_wonder\_what\_happens\_when\_you\_trade\_strict/](https://www.reddit.com/r/oasisnetwork/comments/1nq20od/ever_wonder_what_happens_when_you_trade_strict/)  
6. Confidential AI: From SGX to TDX, accessed December 27, 2025, [https://moonboot.dev/article/confidential-ai-from-sgx-to-tdx](https://moonboot.dev/article/confidential-ai-from-sgx-to-tdx)  
7. ‍Introducing TDX Support for the ROFL Framework‍ \- Oasis Protocol, accessed December 27, 2025, [https://oasis.net/blog/tdx-support-rofl](https://oasis.net/blog/tdx-support-rofl)  
8. Init | Oasis Documentation, accessed December 27, 2025, [https://docs.oasis.io/build/rofl/workflow/init/](https://docs.oasis.io/build/rofl/workflow/init/)  
9. A Cup of TEE, Please. But How Do We Know It's The Right Flavor?, accessed December 27, 2025, [https://oasis.net/blog/tees-remote-attestation-process](https://oasis.net/blog/tees-remote-attestation-process)  
10. Troubleshooting | Oasis Documentation, accessed December 27, 2025, [https://docs.oasis.io/node/run-your-node/troubleshooting/](https://docs.oasis.io/node/run-your-node/troubleshooting/)  
11. ROFL | Oasis Documentation, accessed December 27, 2025, [https://docs.oasis.io/general/manage-tokens/cli/rofl/](https://docs.oasis.io/general/manage-tokens/cli/rofl/)  
12. oasisprotocol/wt3: An autonomous trading AI agent built on Oasis ..., accessed December 27, 2025, [https://github.com/oasisprotocol/wt3](https://github.com/oasisprotocol/wt3)  
13. Hardware Requirements | Oasis Documentation, accessed December 27, 2025, [https://docs.oasis.io/node/run-your-node/prerequisites/hardware-recommendations/](https://docs.oasis.io/node/run-your-node/prerequisites/hardware-recommendations/)  
14. Oasis Engineering Update | June 2025, accessed December 27, 2025, [https://oasis.net/blog/engineering-update-june-2025](https://oasis.net/blog/engineering-update-june-2025)  
15. Using Replication and Redundancy for High Availability, accessed December 27, 2025, [https://docs.oracle.com/cd/E19656-01/821-1502/fpcqm/index.html](https://docs.oracle.com/cd/E19656-01/821-1502/fpcqm/index.html)  
16. High-Availability, Redundancy and Fail-Over \- Kolmisoft Blog \-, accessed December 27, 2025, [https://blog.kolmisoft.com/high-availability-redundancy-and-fail-over/](https://blog.kolmisoft.com/high-availability-redundancy-and-fail-over/)  
17. WT3: The Future of Private, Verifiable AI Agents on OasisProtocol ..., accessed December 27, 2025, [https://medium.com/@shegeemankind/wt3-the-future-of-private-verifiable-ai-agents-on-oasisprotocol-sapphire-ff64966f7ff6](https://medium.com/@shegeemankind/wt3-the-future-of-private-verifiable-ai-agents-on-oasisprotocol-sapphire-ff64966f7ff6)  
18. How ROFL and Oasis Are Changing Crypto, AI, and Identity., accessed December 27, 2025, [https://shegeemankind.medium.com/how-rofl-and-oasis-are-changing-crypto-ai-and-identity-8064573bb887](https://shegeemankind.medium.com/how-rofl-and-oasis-are-changing-crypto-ai-and-identity-8064573bb887)  
19. Building Privacy-Preserving Federated AI on ROFL with Flashback ..., accessed December 27, 2025, [https://dev.to/caerlower/building-privacy-preserving-federated-ai-on-rofl-with-flashback-labs-2nae](https://dev.to/caerlower/building-privacy-preserving-federated-ai-on-rofl-with-flashback-labs-2nae)  
20. Oasis & Flashback Labs: Enabling Privacy-First AI Training, accessed December 27, 2025, [https://oasis.net/blog/flashback-privacy-first-ai-training](https://oasis.net/blog/flashback-privacy-first-ai-training)  
21. Deploy | Oasis Documentation \- Oasis Docs, accessed December 27, 2025, [https://docs.oasis.io/build/rofl/workflow/deploy/](https://docs.oasis.io/build/rofl/workflow/deploy/)  
22. Confidential Execution in Oasis Protocol: Technical Architecture of ..., accessed December 27, 2025, [https://medium.com/@caerlower/confidential-execution-in-oasis-protocol-technical-architecture-of-trusted-execution-environments-92dbc629bcfd](https://medium.com/@caerlower/confidential-execution-in-oasis-protocol-technical-architecture-of-trusted-execution-environments-92dbc629bcfd)