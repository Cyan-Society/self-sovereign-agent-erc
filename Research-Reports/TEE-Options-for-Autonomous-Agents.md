# **Secure Foundations for the Autonomous Economy: A Comprehensive Analysis of Trusted Execution Environments for Blockchain Agents**

## **1\. Introduction: The Custody Paradox in Autonomous Agency**

The rapid ascendancy of autonomous agents—software entities capable of reasoning, planning, and executing complex workflows without human intervention—has precipitated a fundamental crisis in digital custody. As these agents evolve from passive information retrieval systems to active economic participants capable of managing decentralized finance (DeFi) portfolios, executing cross-chain arbitrages, and holding localized wallets, the traditional security paradigms of the blockchain ecosystem are rendered insufficient. The core challenge, which we designate as the "Agency-Security Paradox," posits that for an agent to be truly autonomous, it must possess exclusive control over its cryptographic credentials; yet, if the agent operates on standard cloud infrastructure, the private keys are inherently accessible to the infrastructure provider, the operating system kernel, and potentially the developer, thereby negating the property of true autonomy.

This report provides an exhaustive architectural analysis of Trusted Execution Environments (TEEs) as the requisite hardware root of trust for autonomous agents. We examine the hardware landscape, ranging from the memory-page isolation of Intel SGX to the virtualization-based security of AMD SEV-SNP and AWS Nitro Enclaves. Furthermore, we evaluate the emerging layer of "Confidential Computing as a Service" provided by Web3-native protocols such as Lit Protocol, Phala Network, Oasis Network, and Marlin, which abstract the complexities of raw hardware into usable primitives for signing and decryption.

Specific attention is devoted to the integration of these secure enclaves with modern agent orchestration platforms, specifically analyzing the compatibility with E2B sandboxes for an entity possessing significant compute credits. The objective is to define a reference architecture that maximizes the utility of general-purpose compute resources for agent reasoning while delegating high-stakes cryptographic operations to a verifiable, attested, and isolated environment.

## ---

**2\. The Hardware Landscape: Silicon-Level Isolation**

To understand the capabilities and limitations of current confidential computing platforms, one must first dissect the underlying hardware technologies that enable execution isolation. The market is currently dominated by divergent architectural approaches, primarily distinguishable by their isolation granularity—whether they isolate a specific application process, a virtual machine, or an entire coprocessor.

### **2.1 Intel Software Guard Extensions (SGX)**

Intel SGX represents the most mature and widely studied TEE implementation in the commercial market. Introduced with the Skylake microarchitecture, SGX allows a user-level application to instantiate a protected region of memory known as an Enclave. The defining characteristic of SGX is its threat model: it assumes the operating system, the hypervisor, and the BIOS are potentially malicious.1

#### **2.1.1 Architectural Mechanism**

When an application creates an enclave, the CPU allocates a portion of the Enclave Page Cache (EPC). Data within the EPC is encrypted in main memory using the Memory Encryption Engine (MEE). The decryption keys are generated within the processor package during boot and are inaccessible to software, including the kernel.3 Decryption occurs only when the data is loaded into the L1/L2 cache for execution. This architecture affords "application-level isolation," meaning developers must partition their application into trusted (enclave) and untrusted (host) components.

#### **2.1.2 Limitations and Vulnerabilities**

While SGX provides granular security, it has historically suffered from the "EPC limitation." Early implementations were restricted to 128MB or 256MB of protected memory, forcing expensive paging operations for memory-intensive applications—a critical bottleneck for AI agents running Large Language Model (LLM) inference.4 Although modern Xeon Scalable processors utilize SGX2 to support significantly larger enclave sizes (up to 1TB), the legacy of side-channel attacks (e.g., Spectre, Foreshadow, LVI) necessitates rigorous adherence to microcode updates and careful coding practices to prevent data leakage via speculative execution or timing analysis.5

### **2.2 AMD Secure Encrypted Virtualization (SEV-SNP)**

AMD approaches confidential computing through the lens of virtualization. Secure Encrypted Virtualization (SEV), and specifically its latest iteration, SEV-SNP (Secure Nested Paging), encrypts the entire memory of a virtual machine with a unique key managed by the AMD Secure Processor (ASP), a dedicated ARM Cortex-A5 coprocessor embedded within the EPYC CPU die.6

#### **2.2.1 Architectural Mechanism**

Unlike SGX, which requires application refactoring, SEV-SNP enables a "lift-and-shift" model. An entire Guest OS runs inside the encrypted domain. The ASP enforces integrity, preventing the hypervisor from replaying memory, remapping pages, or injecting interrupts to destabilize the guest. This "VM-level isolation" is particularly advantageous for autonomous agents that rely on complex software stacks (e.g., Docker containers, Python runtimes, machine learning libraries) that would be arduous to port to the constrained environment of an SGX enclave.7

#### **2.2.2 Integrity Protections**

The specific advancement of the "SNP" (Secure Nested Paging) extension is pivotal for agent security. Previous versions of SEV encrypted memory but did not fully protect against integrity attacks where a malicious hypervisor could corrupt the guest's memory. SEV-SNP adds strong integrity checks, ensuring that if the hypervisor attempts to write to the guest's memory, the CPU will detect the modification and halt execution, thereby preserving the confidentiality of the agent's private keys.3

### **2.3 AWS Nitro Enclaves**

AWS Nitro Enclaves is a unique hybrid approach that leverages the custom silicon of the AWS Nitro System. Rather than relying solely on general-purpose CPU extensions like SGX or SEV, Nitro Enclaves utilizes the Nitro Card—a dedicated hardware card that offloads virtualization, networking, and storage functions—to create isolated compute environments.4

#### **2.3.1 Architectural Mechanism**

A Nitro Enclave is carved out of a parent EC2 instance. When a user requests an enclave, the Nitro Hypervisor reallocates specific vCPUs and memory regions from the parent instance to the enclave. Crucially, the enclave is stripped of all persistent storage, interactive access (no SSH), and external networking. Communication is restricted solely to a local vsock (virtual socket) connection with the parent instance.8

#### **2.3.2 The Isolation Philosophy**

This architecture enforces a strict "Brain-Wallet" separation by design. The enclave cannot reach the internet to leak keys; it can only respond to signing requests sent by the parent. This reduction of the attack surface—eliminating the network stack and the shell—makes Nitro Enclaves arguably the most secure environment for holding private keys in a cloud context, provided the developer can architect the necessary proxy logic for communication.8

### **2.4 ARM TrustZone**

While primarily associated with mobile and IoT devices, ARM TrustZone partitions the processor into a "Secure World" and a "Normal World." In the context of autonomous agents, TrustZone is less relevant for high-performance server-side agents but is critical for "Edge Agents" running on local devices. However, given the user's focus on $20K credits and E2B (cloud environments), this analysis concentrates on server-grade TEEs (SGX, SEV, Nitro) rather than mobile hardware.2

## ---

**3\. Cloud-Hosted TEE Platforms: Infrastructure-as-a-Service Comparison**

For organizations seeking granular control over their agent's infrastructure, deploying directly on major cloud providers offers the highest degree of sovereignty. However, this comes with significant DevOps overhead. We compare the two leaders in confidential cloud computing: AWS and Microsoft Azure.

### **3.1 AWS Nitro Enclaves: The Sovereign Silo**

AWS Nitro Enclaves functions as a feature of EC2 rather than a distinct instance class. This democratization of security means that any supported EC2 instance (Intel, AMD, or Graviton-based) can spawn an enclave.8

#### **3.1.1 Implementation Architecture**

To deploy an autonomous agent on Nitro, the architecture must be bifurcated:

1. **The Parent Instance:** Runs the agent's reasoning engine (e.g., LangChain, AutoGPT) and maintains the blockchain connection via RPC. This instance has full internet access.  
2. **The Enclave:** Runs the cryptographic signer. It holds the private key in memory. It listens on the vsock for a transaction payload, verifies the payload against a policy (e.g., "Allow transfer only to whitelist addresses"), signs it, and returns the signature to the parent.11

#### **3.1.2 Cost Efficiency and Modeling**

One of the most compelling aspects of AWS Nitro Enclaves is its pricing model: there is **no additional charge** for the enclave itself. The user pays only for the underlying EC2 instance.

* **Resource Carving:** The cost implication arises from resource allocation. If a user provisions a c5.xlarge (4 vCPU, 8 GB RAM) and allocates 2 vCPUs and 4 GB RAM to the enclave, the parent instance is left with only half the capacity. The bill remains that of a standard c5.xlarge.  
* **Comparative Advantage:** Independent analysis suggests that Nitro Enclaves can reduce confidential compute costs by approximately 60% compared to Azure's premium confidential VMs, primarily because users can utilize standard, high-volume instance types rather than specialized, premium-priced hardware.12

#### **3.1.3 Operational Complexity**

The trade-off for this cost efficiency is complexity. Nitro Enclaves do not support a full operating system in the traditional sense; they boot a stripped-down kernel. Developers must build their applications into a specific Enclave Image File (.eif) using the Nitro CLI. Debugging is notoriously difficult as there is no console access; logs must be pushed out via the vsock channel.8

### **3.2 Azure Confidential Computing: The Virtualization Approach**

Microsoft Azure has taken a multi-pronged approach, offering both Intel SGX-based enclaves (DC-series) and AMD SEV-SNP based Confidential VMs.6

#### **3.2.1 Intel SGX on Azure**

Azure's DC-series VMs expose Intel SGX instructions to the guest. This allows developers to use frameworks like Open Enclave SDK to write applications with protected memory regions.

* **Limitations:** Older generations (DCsv2) had severely limited EPC memory (approx. 168 MB), rendering them unsuitable for AI models. Newer DCsv3 instances support much larger EPCs (up to 256 GB), but availability varies by region.4

#### **3.2.2 Confidential VMs (AMD SEV-SNP)**

Azure's flagship offering for "lift-and-shift" workloads is the Confidential VM. Here, the entire VM memory is encrypted.

* **Operational Ease:** Unlike Nitro, a Confidential VM behaves like a standard server. You can SSH into it, install Docker, and run your agent's code without modification. The encryption is transparent to the OS.  
* **Cost Premium:** Azure charges a premium for Confidential VMs compared to standard General Purpose VMs. While precise premiums fluctuate, users should expect a 20-30% increase in hourly rates for the assurance of memory encryption and remote attestation capabilities.13

### **3.3 Comparative Verdict for Agents**

For an autonomous agent developer:

* **AWS Nitro Enclaves** is superior for **Key Management**. Its lack of external networking enforces a security architecture that prevents key exfiltration by design. It is also the most cost-effective solution for high-volume deployments.  
* **Azure Confidential VMs** are superior for **Full Agent Execution**. If the goal is to run the *entire* agent (reasoning \+ signing) inside the TEE to protect the proprietary model weights or strategy logic, Azure's support for full OS encryption via AMD SEV-SNP is the optimal path, despite the higher cost.

## ---

**4\. Web3-Specific TEE Solutions: The "Function-as-a-Service" Layer**

While AWS and Azure offer infrastructure, a new class of Web3 protocols offers "Decentralized Confidential Computing." These platforms abstract the hardware complexity, providing what is essentially "Serverless TEEs" optimized for blockchain interoperability.

### **4.1 Lit Protocol: Decentralized Key Management**

Lit Protocol operates as a decentralized network where nodes run inside TEEs (specifically AMD SEV-SNP).14 It utilizes Threshold Secret Schemes (TSS) to ensure that no single node ever holds the full private key.

#### **4.1.1 Programmable Key Pairs (PKPs) and Lit Actions**

Lit introduces the concept of **Programmable Key Pairs (PKPs)**, which are MPC-based wallets represented as NFTs. The "brain" of the PKP is a **Lit Action**—an immutable JavaScript program stored on IPFS.

* **The Mechanism:** When an agent triggers a Lit Action, the Lit nodes independently execute the JavaScript code inside their TEEs. If the code executes successfully (e.g., verifying that a trade meets risk parameters), the nodes sign the transaction with their key share. These shares are combined on the client side to form a valid signature.15  
* **Agent Utility:** This is a paradigm shift for autonomous agents. The agent does not need to *hold* the key; it holds an authentication token (e.g., a session signature) to *request* the key to sign, subject to the logic defined in the Lit Action. This allows for creating "Guardrailed Agents" where the signing logic is immutable and verifiable.17

#### **4.1.2 Cost Structure: Capacity Credits**

Lit Protocol utilizes a **Capacity Credits** model. Instead of paying gas for every signature, users mint a Capacity Credit NFT that grants a reserved throughput (requests per second) for a specific duration.18

* **Free Tier:** For development and low-volume testing, Lit offers a free tier via their testnet and limited mainnet capacity, making it highly accessible for early-stage agent development.18  
* **Production Cost:** For high-frequency trading agents, developers purchase Capacity Credits. This fixed-cost model is often more predictable than gas-based models and cheaper than maintaining 24/7 EC2 instances if the agent's signing activity is bursty.

### **4.2 Phala Network: Off-Chain Computation**

Phala Network leverages the Polkadot ecosystem to provide "Phat Contracts"—programs that run off-chain in Intel SGX enclaves but can interact with on-chain states.19

#### **4.2.1 Phat Contracts and AI Agents**

Phat Contracts are designed to be the "backend" for Web3 applications. Unlike traditional smart contracts, they have internet access (via HTTP requests initiated from the enclave) and can run heavy computations at near-native speed.21

* **Agent Synergy:** Phala explicitly markets "AI Agent Contracts." A developer can deploy the agent's logic (in JavaScript/TypeScript) to Phala's network. The code runs inside SGX, ensuring execution integrity. The agent can fetch data from Web2 APIs, process it, and sign transactions to any blockchain.22

#### **4.2.2 Economics: Stake-to-Compute**

Phala employs a unique "Stake-to-Compute" tokenomics model. Instead of paying a monthly fee (fiat) or per-transaction gas, developers stake the native token ($PHA) to reserve computing power on the worker nodes.23

* **Cost Analysis:** This model effectively reduces the marginal cost of computation to zero, assuming the capital opportunity cost of staking is acceptable. For a holder of crypto assets, this can be significantly more capital-efficient than the "burn" of AWS monthly bills.

### **4.3 Oasis Network: The Confidential EVM**

Oasis Sapphire is the first confidential EVM (Ethereum Virtual Machine) compatible runtime.24

#### **4.3.1 Smart Privacy**

Sapphire runs the EVM inside SGX enclaves. The key innovation is that the state of the smart contract is encrypted.

* **Usage for Agents:** A developer can deploy a Solidity contract on Sapphire that stores a private key (for Ethereum, Bitcoin, etc.) in its encrypted storage. The contract exposes a function signTransaction(payload) which is gated by on-chain logic (e.g., DAO vote, AI oracle verification).  
* **Pros:** This keeps the entire workflow "on-chain" and accessible via standard Ethereum tooling (Hardhat, Ethers.js).25  
* **Cons:** It is constrained by the performance limits of the EVM and block latency, making it less suitable for high-frequency trading agents or those requiring heavy compute (e.g., ML inference) compared to Phala or Lit.

### **4.4 Marlin Oyster: Serverless Enclaves**

Marlin Oyster offers a platform that bridges the gap between raw AWS Nitro instances and managed Web3 services.26

#### **4.4.1 Architecture and Pricing**

Oyster allows developers to deploy Docker containers directly to a network of TEE nodes (primarily AWS Nitro). It abstracts the complexity of setting up the AWS account and managing the instance.

* **Pricing:** Oyster utilizes a market-based pricing model, typically denominated in USDC or POND tokens.27 Developers pay for the time the enclave is running. This can be competitively priced compared to direct AWS usage due to the decentralized market of resource providers, though it introduces a dependency on the Marlin marketplace liquidity.28

## ---

**5\. E2B Compatibility and the Hybrid Architecture Strategy**

The user explicitly identifies as a holder of **$20,000 in E2B credits**. Maximizing the utility of these credits while ensuring security is the primary optimization objective.

### **5.1 Analyzing E2B's Security Model**

Research confirms that E2B infrastructure is built upon **Firecracker microVMs**.29 Firecracker, developed by AWS, uses KVM to provide lightweight, rapid-booting virtual machines (150ms startup).

* **The TEE Gap:** Crucially, standard Firecracker microVMs are **not** Trusted Execution Environments. While they provide excellent isolation from other tenants, they do not provide memory encryption against the host infrastructure provider. E2B's administrators (or a sophisticated attacker with physical access to E2B's servers) could theoretically dump the memory of a running sandbox and extract any private keys stored therein.30  
* **Conclusion:** It is insecure to store long-term, high-value private keys directly within an E2B sandbox for an autonomous agent.

### **5.2 The Hybrid "Brain-Wallet" Architecture**

To utilize the $20,000 credits effectively, we propose a hybrid architecture that leverages E2B for computation and a separate TEE layer for custody.

#### **5.2.1 The Brain (E2B Sandbox)**

Use E2B for the agent's heavy lifting. The $20k credits allow for massive computational throughput.

* **Tasks:** Running the Python-based LLM orchestration (LangChain/AutoGPT), executing data analysis tools (Pandas/Numpy), formulating transaction payloads, and interacting with the blockchain via RPC.  
* **State:** This environment is ephemeral and stateless regarding credentials. It holds "Authentication Tokens" (e.g., a Lit Session Signature) but not "Private Keys."

#### **5.2.2 The Wallet (TEE Sidecar)**

Use a specialized TEE service to act as the signer.

* **Option A: Lit Protocol (Recommended):** The E2B agent uses the Lit Python SDK to connect to the Lit Network. When it needs to sign a transaction, it sends the payload to Lit. Lit verifies the policy (Lit Action) and returns the signature.  
  * *Compatibility:* High. E2B sandboxes have internet access, allowing seamless API calls to Lit nodes.32  
* **Option B: Phala Phat Contract:** The E2B agent sends an HTTP request to a specific Phat Contract endpoint. The Phat Contract (running in SGX) signs the transaction.  
* **Option C: Self-Hosted Nitro Enclave:** Deploy a minimal Nitro Enclave on AWS (costing \~$100/month). The E2B agent communicates with this enclave via a secure TLS tunnel (Mutual TLS).

### **5.3 Implementation Workflow for the $20K Holder**

1. **Develop Logic on E2B:** Build the agent's core loop in the E2B sandbox. Utilize the fast boot times to spin up agents on demand.  
2. **Integrate Lit Python SDK:** Import the lit-python-sdk into the E2B environment.33  
3. **Mint PKP:** Create a Programmable Key Pair on Lit. Assign the "Brain" (the E2B agent's auth method) as a controller of this PKP.  
4. **Execute:** The agent calculates a trade \-\> Calls lit.execute\_js \-\> Lit Nodes Sign \-\> Signature returned to E2B \-\> Agent broadcasts tx to Ethereum.

This architecture maximizes the $20k credit value (using it for 99% of the compute) while ensuring that the 1% of the operation that requires absolute security (signing) is offloaded to a verified TEE.

## ---

**6\. Practical Considerations: Attestation and Key Management**

Transitioning from theory to practice requires mastering two critical concepts: Remote Attestation and Key Management.

### **6.1 Remote Attestation (RA): The Trust Anchor**

Remote Attestation is the cryptographic process by which a TEE proves to a remote party (the agent) that it is genuine hardware running a specific piece of code.

#### **6.1.1 The AWS Nitro Attestation Process**

In a self-hosted Nitro setup, the attestation flow is manual and rigorous:

1. **Generation:** The enclave calls the Nitro Security Module (NSM) to generate an attestation document. This document is a **CBOR-encoded COSE\_Sign1** object containing the enclave's measurements (PCRs), a timestamp, and a public key, all signed by the Nitro Hypervisor.34  
2. **Verification:** The client (running on E2B) receives this document. It must:  
   * Decode the CBOR structure.35  
   * Verify the COSE signature using the AWS Nitro Root Certificate (downloaded from AWS).  
   * Compare the **PCR0** value (the SHA384 hash of the Enclave Image File) against the expected hash of the code you compiled.  
   * Compare the **PCR4** value (Instance ID) to ensure it is running on the specific EC2 instance you control.36  
3. **Code Example (Conceptual):**  
   Python  
   import cbor2  
   from cose.messages import Sign1Message  
   \#... verify signature logic...  
   payload \= cbor2.loads(cose\_msg.payload)  
   if payload\['pcr0'\].hex()\!= EXPECTED\_HASH:  
       raise SecurityException("Enclave code modified\!")

#### **6.1.2 The Web3 Attestation Shortcut**

Protocols like Lit and Phala abstract this. The nodes in the network perform mutual attestation before joining the consensus. The user implicitly trusts the network's consensus mechanism or validates a master certificate, significantly reducing the coding burden on the agent developer.37

### **6.2 Key Management Strategies**

How does the key get into the enclave?

#### **6.2.1 Generate-in-Enclave (Maximum Security)**

The enclave generates the key pair locally using a hardware TRNG (True Random Number Generator). The private key *never* leaves the enclave memory.

* **Risk:** If the enclave crashes or the instance is terminated, the key is lost forever.  
* **Solution:** **Key Wrapping.** The enclave generates the key, then encrypts (wraps) it with a master key derived from the enclave's unique identity (sealing). It outputs the encrypted blob to S3/IPFS. To restore, the new enclave reads the blob; only an enclave with the exact same code (PCRs) can decrypt it.8

#### **6.2.2 Distributed Key Generation (DKG)**

Used by Lit and Phala. The key is generated cooperatively by multiple TEE nodes. No single machine sees the private key.

* **Benefit:** This provides fault tolerance. If one node goes offline, the key is not lost. It is the preferred method for high-value autonomous agents as it eliminates the "single point of failure" inherent in self-hosted enclaves.14

## ---

**7\. Comparative Analysis and Cost Tables**

### **7.1 Feature Comparison Matrix**

| Feature | AWS Nitro Enclaves | Azure Confidential VM | Lit Protocol | Phala Network | Marlin Oyster |
| :---- | :---- | :---- | :---- | :---- | :---- |
| **TEE Hardware** | AWS Nitro (Custom) | Intel SGX / AMD SEV-SNP | AMD SEV-SNP | Intel SGX | AWS Nitro |
| **Isolation Level** | Enclave (No Network/Shell) | Virtual Machine (Full OS) | Node (Managed Service) | Wasm Contract | Container |
| **Ease of Use** | Low (Requires vsock coding) | High (Standard VM) | Very High (SDKs) | Moderate (JS/Rust) | Moderate (Docker) |
| **Key Mgmt** | Self-Managed (Local Gen) | Self-Managed | DKG (Network Managed) | DKG / Local | Self-Managed |
| **Cost Model** | Hourly (EC2 only) | Hourly (Premium VM) | Capacity Credits (NFTs) | Staking ($PHA) | Market (USDC/POND) |
| **Agent Suitability** | High Security / Sovereignty | Legacy App Migration | Crypto-Native / DeFi | Off-chain Compute | Serverless Backend |

### **7.2 Cost Comparison Scenarios**

**Scenario:** An autonomous agent running 24/7, signing 100 transactions per day.

| Platform | Estimated Monthly Cost | Calculation Logic |
| :---- | :---- | :---- |
| **AWS Nitro** | **$120 \- $150** | Based on c6i.xlarge (4 vCPU) running 24/7. Enclave is free. |
| **Azure Conf. VM** | **$180 \- $220** | DC-series VMs carry \~20-30% premium over standard compute. |
| **Lit Protocol** | **\<$50 (or Free)** | 100 sigs/day is low volume. Likely covered by free tier or minimal Capacity Credit NFT. |
| **Phala Network** | **\~$0 (Opportunity Cost)** | Requires staking \~$500-$1000 worth of PHA tokens. Principal is recoverable. |
| **Marlin Oyster** | **$100 \- $130** | Market rates for Nitro instances \+ Marlin service fee. |

## ---

**8\. Conclusion and Strategic Recommendations**

The selection of a Trusted Execution Environment for an autonomous agent is a trade-off between **sovereignty**, **complexity**, and **cost**.

For an entity possessing **$20,000 in E2B credits**, the optimal strategy is **hybridization**:

1. **Maximize E2B:** Utilize the E2B Firecracker sandboxes for the "Brain" of the agent. Run the heavy LLM inference, data processing, and strategy formulation here. This burns the credits efficiently on the workload they are designed for.  
2. **Outsource Custody:** Do *not* store keys on E2B. Instead, integrate the **Lit Protocol Python SDK**. Mint a Programmable Key Pair (PKP) and use Lit Actions to define the signing policy. This delegates the security-critical signing to a decentralized TEE network that is specifically optimized for this task.  
3. **Fallback/Sovereign Option:** If decentralized networks (Lit/Phala) present an unacceptable counterparty risk, deploy a single, minimal **AWS Nitro Enclave** (e.g., c6i.large) to act as a dedicated "Signing Server." Build a secure tunnel between the E2B instances and this signer.

**Final Verdict:**

* **Best for Developer Velocity:** Lit Protocol (Abstracts hardware, integrates easily with Python/JS).  
* **Best for Security Maximalists:** AWS Nitro Enclaves (Minimal attack surface, verified by the user).  
* **Best for Cost Optimization:** Phala Network (Staking model removes monthly opex).

By strictly adhering to the "Brain-Wallet" separation architecture, developers can deploy autonomous agents that are both computationally powerful and cryptographically secure, fully unlocking the potential of the autonomous economy.

#### **Works cited**

1. What Is Confidential Computing? \- IBM, accessed December 21, 2025, [https://www.ibm.com/think/topics/confidential-computing](https://www.ibm.com/think/topics/confidential-computing)  
2. Trusted Execution Environments in Web3: A Comprehensive Guide ..., accessed December 21, 2025, [https://metaschool.so/articles/trusted-execution-environments-tees](https://metaschool.so/articles/trusted-execution-environments-tees)  
3. Comparative Review of AWS and Azure Confidential Computing ..., accessed December 21, 2025, [https://jisem-journal.com/index.php/journal/article/download/1805/695/2908](https://jisem-journal.com/index.php/journal/article/download/1805/695/2908)  
4. Comparative Review of AWS and Azure Confidential Computing ..., accessed December 21, 2025, [https://www.researchgate.net/publication/389658299\_Comparative\_Review\_of\_AWS\_and\_Azure\_Confidential\_Computing\_Systems](https://www.researchgate.net/publication/389658299_Comparative_Review_of_AWS_and_Azure_Confidential_Computing_Systems)  
5. Trusted Execution Environments (TEEs): Ensuring Security and ..., accessed December 21, 2025, [https://sisustake.medium.com/trusted-execution-environments-tees-ensuring-security-and-privacy-in-blockchain-and-smart-6947dde13cf3](https://sisustake.medium.com/trusted-execution-environments-tees-ensuring-security-and-privacy-in-blockchain-and-smart-6947dde13cf3)  
6. Trusted Execution Environment (TEE) \- Microsoft Learn, accessed December 21, 2025, [https://learn.microsoft.com/en-us/azure/confidential-computing/trusted-execution-environment](https://learn.microsoft.com/en-us/azure/confidential-computing/trusted-execution-environment)  
7. Confidential Computing has Become the Backbone of Secure AI, accessed December 21, 2025, [https://www.corvex.ai/blog/confidential-computing-the-backbone-of-secure-ai](https://www.corvex.ai/blog/confidential-computing-the-backbone-of-secure-ai)  
8. AWS Nitro Enclaves, accessed December 21, 2025, [https://aws.amazon.com/ec2/nitro/nitro-enclaves/](https://aws.amazon.com/ec2/nitro/nitro-enclaves/)  
9. Blogs \- Cloudride, accessed December 21, 2025, [https://www.cloudride.co.il/blog/all](https://www.cloudride.co.il/blog/all)  
10. Compare AWS Nitro Enclaves vs. Azure Confidential Ledger in 2025, accessed December 21, 2025, [https://slashdot.org/software/comparison/AWS-Nitro-Enclaves-vs-Azure-Confidential-Ledger/](https://slashdot.org/software/comparison/AWS-Nitro-Enclaves-vs-Azure-Confidential-Ledger/)  
11. How I Learned to Perform Security Testing on AWS Using Nitro ..., accessed December 21, 2025, [https://medium.com/@davebhargavi507/how-i-learned-to-perform-security-testing-on-aws-using-nitro-enclaves-f60d0e0b82fb](https://medium.com/@davebhargavi507/how-i-learned-to-perform-security-testing-on-aws-using-nitro-enclaves-f60d0e0b82fb)  
12. Azure confidential computing alternatives? pricing is killing us \- Reddit, accessed December 21, 2025, [https://www.reddit.com/r/AZURE/comments/1p1533x/azure\_confidential\_computing\_alternatives\_pricing/](https://www.reddit.com/r/AZURE/comments/1p1533x/azure_confidential_computing_alternatives_pricing/)  
13. Azure vs AWS Pricing: Comparing Apples to Apples | NetApp, accessed December 21, 2025, [https://www.netapp.com/blog/azure-vs-aws-pricing-comparing-apples-to-apples-azure-aws-cvo-blg/](https://www.netapp.com/blog/azure-vs-aws-pricing-comparing-apples-to-apples-azure-aws-cvo-blg/)  
14. Lit Protocol: Towards Autonomy on the User-Owned Web \- Medium, accessed December 21, 2025, [https://medium.com/1kxnetwork/lit-protocol-towards-autonomy-on-the-user-owned-web-ad84905210a9](https://medium.com/1kxnetwork/lit-protocol-towards-autonomy-on-the-user-owned-web-ad84905210a9)  
15. Spark by Lit Protocol: Building the Foundation for a Decentralized ..., accessed December 21, 2025, [https://medium.com/@0xdeadpoet/spark-by-lit-protocol-building-the-foundation-for-a-decentralized-future-e6a4e90d75fc](https://medium.com/@0xdeadpoet/spark-by-lit-protocol-building-the-foundation-for-a-decentralized-future-e6a4e90d75fc)  
16. Unlocking New Possibilities: Sign and Decrypt within Lit Actions, accessed December 21, 2025, [https://spark.litprotocol.com/unlocking-new-possibilities-with-lit-actions/](https://spark.litprotocol.com/unlocking-new-possibilities-with-lit-actions/)  
17. What is Lit Protocol? Core Infrastructure for Programmable Key ..., accessed December 21, 2025, [https://www.mexc.co/learn/article/what-is-lit-protocol-core-infrastructure-for-programmable-key-management-in-web3/1](https://www.mexc.co/learn/article/what-is-lit-protocol-core-infrastructure-for-programmable-key-management-in-web3/1)  
18. Paying for Usage of Lit \- Lit Protocol, accessed December 21, 2025, [https://developer.litprotocol.com/paying-for-lit/overview](https://developer.litprotocol.com/paying-for-lit/overview)  
19. Private AI Agents \- Autonomous Agents with TEE \- Phala Network, accessed December 21, 2025, [https://phala.com/solutions/ai-agents](https://phala.com/solutions/ai-agents)  
20. Phala Network Guide, accessed December 21, 2025, [https://truepositiontools.com/crypto/phala-network-guide.html](https://truepositiontools.com/crypto/phala-network-guide.html)  
21. Phala Network. FAQ\! \- Medium, accessed December 21, 2025, [https://medium.com/@PhalaUkraine/phala-network-faq-00558e4c49be](https://medium.com/@PhalaUkraine/phala-network-faq-00558e4c49be)  
22. Phala-Network/phat-contract-starter-kit \- GitHub, accessed December 21, 2025, [https://github.com/Phala-Network/phat-contract-starter-kit](https://github.com/Phala-Network/phat-contract-starter-kit)  
23. Revolutionary Stake-to-Compute Model Takes the Stage with Phat ..., accessed December 21, 2025, [https://phalanetwork.medium.com/revolutionary-stake-to-compute-model-takes-the-stage-with-phat-contracts-latest-tokenomic-update-c9bcef4d6d83](https://phalanetwork.medium.com/revolutionary-stake-to-compute-model-takes-the-stage-with-phat-contracts-latest-tokenomic-update-c9bcef4d6d83)  
24. WT3: The Future of Private, Verifiable AI Agents on OasisProtocol ..., accessed December 21, 2025, [https://medium.com/@shegeemankind/wt3-the-future-of-private-verifiable-ai-agents-on-oasisprotocol-sapphire-ff64966f7ff6](https://medium.com/@shegeemankind/wt3-the-future-of-private-verifiable-ai-agents-on-oasisprotocol-sapphire-ff64966f7ff6)  
25. Oasis Sapphire, accessed December 21, 2025, [https://oasis.net/sapphire](https://oasis.net/sapphire)  
26. Introduction to Marlin | Welcome to the Marlin docs\!, accessed December 21, 2025, [https://docs.marlin.org/oyster/introduction-to-marlin/](https://docs.marlin.org/oyster/introduction-to-marlin/)  
27. User Interface | Welcome to the Marlin docs\!, accessed December 21, 2025, [https://docs.marlin.org/user-guides/oyster/ui](https://docs.marlin.org/user-guides/oyster/ui)  
28. Marlin \- Decentralized Finance | IQ.wiki, accessed December 21, 2025, [https://iq.wiki/wiki/marlin](https://iq.wiki/wiki/marlin)  
29. E2B (Python) MCP Server: An AI Engineer's Deep Dive, accessed December 21, 2025, [https://skywork.ai/skypage/en/ai-engineer-deep-dive/1978019564182491136](https://skywork.ai/skypage/en/ai-engineer-deep-dive/1978019564182491136)  
30. Firecracker vs QEMU — E2B Blog, accessed December 21, 2025, [https://e2b.dev/blog/firecracker-vs-qemu](https://e2b.dev/blog/firecracker-vs-qemu)  
31. E2b breakdown \- Dwarves Memo, accessed December 21, 2025, [https://memo.d.foundation/breakdown/e2b](https://memo.d.foundation/breakdown/e2b)  
32. The New Era of Cloud Agent Infrastructure: In-Depth Analysis of E2B ..., accessed December 21, 2025, [https://jimmysong.io/blog/e2b-browserbase-report/](https://jimmysong.io/blog/e2b-browserbase-report/)  
33. lit-python-sdk \- PyPI, accessed December 21, 2025, [https://pypi.org/project/lit-python-sdk/](https://pypi.org/project/lit-python-sdk/)  
34. Validating attestation documents produced by AWS Nitro Enclaves, accessed December 21, 2025, [https://aws.amazon.com/blogs/compute/validating-attestation-documents-produced-by-aws-nitro-enclaves/](https://aws.amazon.com/blogs/compute/validating-attestation-documents-produced-by-aws-nitro-enclaves/)  
35. How to Use AWS Nitro Enclaves Attestation Document, accessed December 21, 2025, [https://dev.to/aws-builders/how-to-use-aws-nitro-enclaves-attestation-document-2376](https://dev.to/aws-builders/how-to-use-aws-nitro-enclaves-attestation-document-2376)  
36. Cryptographic attestation \- AWS Nitro Enclaves, accessed December 21, 2025, [https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html](https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html)  
37. Phala-Network/phat-pod-tools \- GitHub, accessed December 21, 2025, [https://github.com/Phala-Network/phat-pod-tools](https://github.com/Phala-Network/phat-pod-tools)  
38. Unveiling the Magic of LIT Network: Decoding Programmable Key ..., accessed December 21, 2025, [https://medium.com/@black\_Diamond/unveiling-the-magic-of-lit-network-decoding-programmable-key-pairs-for-the-digital-age-8b94184b7779](https://medium.com/@black_Diamond/unveiling-the-magic-of-lit-network-decoding-programmable-key-pairs-for-the-digital-age-8b94184b7779)