# **Confidential Computing Architectures for Autonomous AI Agent Memory Protection: A Deep Analysis of TEEs and Privacy-Preserving Technologies**

## **1\. The Imperative for Sovereign Memory in Autonomous Systems**

The rapid evolution of artificial intelligence has transitioned from transient, stateless inference models to persistent, autonomous agents. Unlike a chatbot that resets its context with every session, an autonomous agent is defined by its continuity. It possesses a long-term memory—often stored in vector databases for semantic retrieval or relational systems like PostgreSQL for transactional state—that encompasses user secrets, learned behavioral preferences, financial authorizations, and historical decision trees. This state constitutes the agent's digital identity.

However, this persistence introduces a profound architectural vulnerability. In traditional cloud environments, while data may be encrypted at rest (on disk) and in transit (over the network), it remains exposed in plaintext during execution. This "data-in-use" gap means that the memory of an autonomous agent is visible to the infrastructure operator. A cloud provider administrator with root access to the hypervisor, or a malicious actor who has compromised the host operating system, can perform a memory dump to extract API keys, private user data, or the agent's internal reasoning logic.

For an autonomous agent to be truly "self-sovereign"—meaning it serves only its owner and cannot be manipulated or inspected by the platform it runs on—the root of trust must be shifted away from the cloud operator's software stack and anchored in the hardware silicon itself. This is the domain of Confidential Computing.

This report provides an exhaustive technical survey of the architectures available to create a "black box" runtime for a Python and PostgreSQL technology stack. It rigorously examines Trusted Execution Environments (TEEs) including Intel Software Guard Extensions (SGX), AMD Secure Encrypted Virtualization (SEV), and AWS Nitro Enclaves, alongside emerging cryptographic alternatives like Fully Homomorphic Encryption (FHE) and decentralized networks like Oasis. The analysis prioritizes practical deployment realities, focusing on how to run unmodified applications, achieve verifiable integrity through attestation, and ensure that the agent's memory remains an opaque secret to the outside world.

## **2\. Threat Modeling for Autonomous Agents**

To understand the necessity of TEEs, one must first dissect the threat model specific to stateful autonomous agents. The agent is assumed to be running on "untrusted infrastructure." This definition of untrusted includes:

1. **The Cloud Provider:** The entity owning the physical servers (e.g., AWS, Azure, Google Cloud). They possess physical access to the memory bus and administrative access to the hypervisor.  
2. **The Host Operating System:** The kernel managing the resources. If compromised by a rootkit or a malicious administrator, the OS can read the virtual memory pages of any user-space process.  
3. **The Hypervisor:** The virtualization layer (e.g., KVM, Xen). It controls the execution of virtual machines and can inspect their register state and RAM.  
4. **Peripheral Devices:** DMA (Direct Memory Access) attacks from network cards or storage controllers can be used to read system memory without CPU intervention.

In a standard deployment, a Python agent connecting to a PostgreSQL database exposes its entire state to all these entities. The Python interpreter holds variables in heap memory in plaintext. The PostgreSQL buffer pool caches table rows in RAM in plaintext. A "cold boot" attack or a live memory snapshot captures this state instantly.

The goal of the architectures detailed in this report is to remove all the above entities from the Trusted Computing Base (TCB). The only trusted components should be:

* The **Hardware Manufacturer** (e.g., Intel, AMD) who bakes the cryptographic keys into the silicon.  
* The **Agent Developer**, who signs the application code.  
* The **Agent Code** itself, which is verified via remote attestation.

## **3\. Trusted Execution Environments (TEEs): The Hardware Foundation**

TEEs provide the physical and logical isolation necessary to protect memory during execution. While they share a common goal, their implementation philosophies differ radically, influencing their suitability for a "black box" Python and PostgreSQL runtime.

### **3.1 Intel Software Guard Extensions (SGX)**

Intel SGX represents the most granular approach to confidential computing, focusing on process-level isolation. It allows an application to instantiate a protected region of memory known as an *enclave*.

#### **3.1.1 Architectural Mechanisms**

SGX functions by setting aside a reserved portion of physical RAM known as the Enclave Page Cache (EPC). This memory is encrypted by the Memory Encryption Engine (MEE) located directly on the CPU package.

* **Memory Encryption:** Data moving from the CPU caches to the EPC is encrypted and integrity-protected. If the OS or hypervisor attempts to read a memory page belonging to an enclave, the memory controller returns random data or 0xFF.  
* **Access Control:** The CPU enforces strict access control. Code executing outside the enclave (Ring 0 kernel or Ring 3 user app) cannot address memory inside the enclave. The enclave, however, can read host memory, allowing for communication buffers.1  
* **Trusted Computing Base:** The TCB is minimal. It includes only the CPU package and the code running inside the enclave. The BIOS, Host OS, and Hypervisor are untrusted. This makes SGX highly resilient to privileged malware or compromised cloud administrators.3

#### **3.1.2 The Memory Limitation (EPC)**

Historically, a major limitation of SGX was the size of the EPC (often limited to 128MB or 256MB on consumer hardware). When an application's working set exceeded this size, the secure paging mechanism (swapping encrypted pages to disk) introduced massive performance penalties, often slowing applications by orders of magnitude.

* **SGX2 and Scalability:** Modern server-grade CPUs (Intel Xeon Scalable "Ice Lake" and newer) support SGX2 with significantly larger EPCs, scaling up to 512GB or 1TB per socket. This evolution is critical for autonomous agents, as Python runtimes and PostgreSQL buffer pools are memory-intensive. For a Python agent utilizing heavy libraries (e.g., NumPy, PyTorch for inference) and a persistent database, deploying on SGX2 hardware is a strict requirement to maintain acceptable latency.4

#### **3.1.3 Application Compatibility: The LibOS Necessity**

SGX natively supports only a restricted subset of CPU instructions. It does not support standard system calls (like open, fork, socket) because executing a system call requires context-switching to the untrusted OS kernel, which breaks the security boundary.

* **The Problem:** Standard Python and PostgreSQL binaries are heavily dependent on system calls. PostgreSQL, for instance, relies on fork() for process management and standard file I/O for persistence. Rewriting PostgreSQL to be "SGX-native" is practically impossible.  
* **The Solution (Library OS):** To run unmodified applications, a Library OS (LibOS) is required. The LibOS runs inside the enclave and implements a compatibility layer. When the Python application calls open(), the LibOS intercepts the call. If it relates to a protected file, the LibOS handles encryption/decryption internally. If it requires host resources (like network sockets), the LibOS marshals the data, performs an "OCALL" (Outside Call) to the untrusted host, and strictly validates the return values to prevent "Iago attacks" (where a malicious kernel returns plausible but incorrect data to confuse the app).5

### **3.2 AMD Secure Encrypted Virtualization (SEV-SNP)**

AMD SEV (Secure Encrypted Virtualization) takes a coarser-grained approach, encrypting the entire Virtual Machine (VM) rather than individual processes.

#### **3.2.1 VM-Level Isolation**

In the SEV model, the memory controller encrypts all RAM associated with a specific VM using a key unique to that VM. This key is generated and managed by the AMD Secure Processor (ASP)—a dedicated ARM Cortex-A5 coprocessor integrated into the EPYC SoC—and is never exposed to the host CPU or hypervisor.8

* **SEV-ES (Encrypted State):** Protects CPU register contents when a VM stops running (context switch), preventing the hypervisor from reading register data.  
* **SEV-SNP (Secure Nested Paging):** The most recent and vital enhancement for autonomous agents. SNP adds strong integrity protection. It prevents the hypervisor from performing "replay attacks" (mapping old encrypted memory pages to the guest to roll back state) or memory remapping attacks. For a database like PostgreSQL, protection against state rollback is non-negotiable; without SNP, a malicious host could silently revert the agent's memory to a previous state.8

#### **3.2.2 The "Lift and Shift" Advantage**

The primary advantage of SEV-SNP is transparency. Because the encryption happens at the virtualization layer, the Guest OS (e.g., Ubuntu running inside the VM) does not need to be heavily modified.

* **Unmodified Stack:** A standard Docker container running Python and PostgreSQL can be deployed into an SEV-SNP VM without recompilation or manifest configuration. The Guest OS kernel sees "plaintext" RAM, while the outside world sees ciphertext.  
* **TCB Trade-off:** The trade-off is a larger TCB. In SGX, you trust only your code. In SEV-SNP, you trust your code *plus* the entire Guest Operating System kernel. If the Guest OS has a vulnerability (e.g., a buffer overflow in the kernel network stack), the agent's memory could be compromised from *within* the VM, even if the hypervisor is locked out.9

### **3.3 AWS Nitro Enclaves**

AWS Nitro Enclaves is a cloud-specific TEE implementation that leverages the AWS Nitro System hardware.

#### **3.3.1 Hypervisor-Level Partitioning**

A Nitro Enclave is not a standard VM; it is a stripped-down, hardened execution environment carved out of a "Parent" EC2 instance.

* **Isolation:** The Nitro Hypervisor legally separates CPU cores and memory regions from the Parent instance and assigns them to the Enclave. The Enclave has no persistent storage, no external networking, and no interactive access (no SSH, no shell).  
* **Communication:** The only channel in or out of the enclave is a local VSOCK (Virtual Socket) connection to the Parent instance. This effectively air-gaps the enclave from the network, forcing all data ingress/egress to be proxied by the Parent.10

#### **3.3.2 The Persistence Challenge for PostgreSQL**

The lack of persistent storage is a critical hurdle for running PostgreSQL in a Nitro Enclave.

* **Ephemeral State:** When a Nitro Enclave terminates, its memory is wiped. A standard PostgreSQL installation would lose all data.  
* **Architectural Workarounds:** To run a stateful agent, one must implement an "Encrypted Block Store" over VSOCK. The PostgreSQL process inside the enclave would write to a virtual block device or a FUSE file system that encrypts data chunks and sends them via VSOCK to the Parent instance for storage on EBS or S3. Upon boot, the enclave must authenticate, retrieve the encrypted blobs, and reconstruct the database state in RAM.12 This is complex to implement compared to Gramine's transparent file system encryption (discussed later).

## **4\. Runtime Environments for "Black Box" Execution**

To run Python and PostgreSQL in these environments without rewriting them, we rely on specialized runtime wrappers.

### **4.1 Gramine (The Gold Standard for SGX)**

Gramine is an open-source Library OS that is widely considered the standard for running unmodified Linux applications on SGX.

#### **4.1.1 Transparent File Encryption**

For an autonomous agent with a database, Gramine's most critical feature is its *Protected File System*.

* **Manifest Configuration:** In the Gramine manifest (python.manifest), the operator defines mount points. A specific directory (e.g., /var/lib/postgresql/data) can be designated as type \= "encrypted".  
* **Mechanism:** When PostgreSQL issues a write() syscall to this directory, Gramine intercepts it. It splits the data into 4KB chunks, encrypts each chunk with an enclave-specific key (or a wrapped key), generates a Merkle tree hash for integrity, and writes the encrypted blob to the untrusted host disk.  
* **Result:** The host sees a file structure, but the contents are high-entropy noise. If the host attempts to modify a file, the Merkle tree verification fails upon the next read, causing Gramine to terminate the enclave to prevent data corruption. This allows PostgreSQL to persist data securely on an untrusted server.14

#### **4.1.2 Networking and Shared Memory**

PostgreSQL relies heavily on shm\_open (Shared Memory) for inter-process communication. SGX does not support host-backed shared memory securely. Gramine emulates this by allocating shared regions within the enclave's encrypted memory, allowing the multi-process PostgreSQL architecture to function without exposing data.

* **Network Allowlisting:** Gramine's manifest allows defining a network policy. While the host handles the TCP/IP stack, the enclave can be configured to only allow connections to specific IPs or ports. Furthermore, Gramine supports "RA-TLS" (Remote Attestation TLS), where the TLS handshake includes the enclave's attestation report, proving to the client that they are connecting to a genuine enclave.4

### **4.2 Occlum**

Occlum is another LibOS option, written in Rust. It utilizes a "Multi-process, Single-address-space" architecture.

* **Performance:** Occlum can be faster for process-heavy workloads like PostgreSQL because it implements fork() efficiently within the enclave address space, avoiding expensive context switches.  
* **Usability:** However, Gramine generally offers a more seamless configuration experience for complex dynamic languages like Python, with better support for glibc quirks.16

### **4.3 Reproducible Builds and Supply Chain Security**

For a TEE to be trustworthy, the binary running inside it must be verifiable. This requires **Deterministic Builds**.

* **AWS Nitro:** The nitro-cli build-enclave command converts a Docker image into an EIF (Enclave Image File). To ensure the measurement (PCR0) is consistent, the build process must be deterministic. Tools like monzo/aws-nitro-util allow building EIFs using **Nix**, which guarantees bit-for-bit reproducibility, eliminating the "it works on my machine" variance that changes cryptographic hashes.18  
* **Gramine:** Gramine's gramine-sgx-sign tool generates a SIGSTRUCT containing the MRENCLAVE. To ensure this hash is reproducible, the underlying shared libraries and Python scripts must not change. Using "Gramine Shielded Containers" (GSC) helps verify that a specific Docker image digest results in a specific Enclave measurement.20

## **5\. Attestation: The Bridge of Trust**

Attestation is the cryptographic backbone of confidential computing. It is the mechanism by which the hardware proves to a remote party (the user or another agent) that it is running the expected code.

### **5.1 SGX Attestation Flow (DCAP)**

For a self-sovereign agent, reliance on Intel's centralized attestation service (IAS) is a bottleneck/privacy risk. The modern standard, **DCAP (Data Center Attestation Primitives)**, allows for self-hosted verification.

1. **Generation:** The agent inside the enclave requests a "Report" from the CPU. This report contains the MRENCLAVE (code hash) and MRSIGNER (developer key hash). It also includes a UserData field where the agent inserts a nonce or the public key of an ephemeral TLS certificate.22  
2. **Signing:** The report is sent to a special "Quoting Enclave" (provided by Intel) on the host, which signs it with a platform-specific key (PCK) to create a "Quote."  
3. **Verification:** The remote user receives the Quote. Instead of calling Intel, they verify the PCK signature chain against cached Intel certificates (PCCS) running on their own infrastructure. This allows fully offline or private verification.23

### **5.2 AWS Nitro Attestation Flow**

Nitro uses a simpler, hypervisor-mediated flow.

1. **Request:** The Python code calls the Nitro Security Module (NSM) via /dev/nsm to request an attestation document. It passes a public\_key or nonce to bind the document to the current session.24  
2. **Document Structure:** The hypervisor returns a CBOR-encoded document signed by AWS. This document contains PCR0 (Image Hash), PCR1 (Kernel/Boot Hash), and PCR4 (Instance ID).25  
3. **Verification:** The recipient uses the AWS root certificate to verify the signature. They then check that PCR0 matches the known hash of the agent's build. Crucially, Nitro integrates with AWS KMS. A KMS Key Policy can be set to kms:RecipientAttestation:ImageSha384, meaning KMS will *only* decrypt a secret key if the request comes from a valid, attested enclave running the correct code.26

## **6\. Cryptographic Alternatives: When Hardware Trust is Insufficient**

While TEEs are powerful, they require trusting the hardware vendor (Intel/AMD/AWS). Cryptographic alternatives offer software-based privacy.

### **6.1 Fully Homomorphic Encryption (FHE)**

FHE allows computation on encrypted data. Ideally, a PostgreSQL database would store FHE-encrypted data, and the Python agent would query it without ever decrypting.

* **Status of Implementation:** Libraries like Concrete-ML (Zama) and PyFHE enable FHE in Python. There is an experimental PostgreSQL extension, pg\_fhe (based on Microsoft SEAL), which allows basic arithmetic on encrypted columns.27  
* **The Blocking Factor:** FHE is computationally prohibitive for the complex logic of an autonomous agent. A simple encrypted multiplication can be 1,000x to 10,000x slower than plaintext. Furthermore, relational logic (SQL JOIN, WHERE clauses based on comparisons) is extremely difficult in FHE because comparison operations on encrypted data are expensive and non-trivial. While FHE is promising for simple aggregations, it cannot yet support a "Black Box" runtime for a general-purpose agent.28

### **6.2 Secure Multi-Party Computation (SMPC)**

SMPC splits data into "shares" distributed among non-colluding parties (e.g., three different servers). Computation is performed by exchanging messages between servers.

* **Relevance:** Useful for swarm intelligence where multiple agents must agree on a decision without revealing their private inputs.30  
* **Stateful Limitations:** SMPC is generally stateless. Adapting a stateful ACID database like PostgreSQL to run over an SMPC protocol is an immense engineering challenge involving high network latency for every read/write operation. It is currently impractical for a responsive autonomous agent.32

## **7\. Decentralized Architectures: Oasis and Secret Network**

Between pure hardware TEEs and pure cryptography lies the "DeCC" (Decentralized Confidential Compute) model, which combines TEEs with blockchain consensus.

### **7.1 Oasis Network (ROFL)**

Oasis has introduced **ROFL (Runtime Off-Chain Logic)**, a framework specifically for this "Black Box Agent" use case.

* **Architecture:** It allows developers to deploy arbitrary containerized applications (like the Python agent) to run inside TEEs (SGX/TDX) on Oasis validator nodes.  
* **The "Trustless AWS":** Instead of managing the TEE infrastructure yourself, you deploy the app to the network. The Oasis consensus layer handles the remote attestation, verifying that the node is running the correct ROFL binary before allowing it to register.  
* **Network Access & Keys:** Unlike bare-metal SGX which is often air-gapped, ROFL apps can be configured with an egress allowlist (to query web APIs). The network also provides a decentralized Key Manager, allowing the agent to request secrets (like API keys) that are encrypted and only accessible inside the verifiable TEE.33  
* **Persistence:** The agent can commit encrypted state hashes back to the Sapphire chain, creating an immutable, verifiable audit trail of its memory evolution.36

### **7.2 Secret Network**

Secret Network focuses on smart contracts (CosmWasm) running inside SGX. While powerful for transactional logic, it is less flexible than Oasis ROFL for running a full, unmodified Python/Postgres stack, as it requires rewriting logic into Rust-based contracts compatible with the chain's WASM engine.37

## **8\. Practical Deployment: The "Self-Sovereign" Architecture**

Based on the survey, the optimal architecture for a self-sovereign, open-source, "black box" agent is **Intel SGX utilizing Gramine**. This provides the best balance of performance, persistence, and unmodified application support.

### **8.1 Recommended Architecture Specifications**

* **Infrastructure:** Bare-metal server or SGX-enabled VM (e.g., Azure DC-series) with SGX2 support (for large memory capacity).  
* **Runtime Stack:**  
  * **LibOS:** Gramine (v1.5+).  
  * **Application:** Standard Python 3.11 interpreter.  
  * **Database:** Standard PostgreSQL 15 binary.  
* **Memory Protection Strategy:**  
  1. **Encrypted File System:** Mount /var/lib/postgresql/data as a encrypted type in the Gramine manifest. This ensures the database on disk is always opaque.14  
  2. **Internal Shared Memory:** Configure Gramine to emulate /dev/shm internally to support Postgres's multi-process coordination without exposing IPC to the host.39  
  3. **Network Shielding:** Bind PostgreSQL to 127.0.0.1 inside the enclave. The Python agent connects via loopback. External access is blocked or strictly tunnelled via RA-TLS.

### **8.2 Configuration Blueprint (Gramine Manifest)**

A simplified python.manifest.template for this architecture would utilize the following critical directives:

| Directive | Value | Purpose |
| :---- | :---- | :---- |
| loader.entrypoint | file:/usr/lib/x86\_64-linux-gnu/gramine/libsysdb.so | Main Gramine loader. |
| libos.entrypoint | /usr/bin/python3 | The trusted application. |
| sgx.enclave\_size | 16G | Large heap for AI logic \+ DB buffer. |
| fs.mounts.type | encrypted | **Critical:** Designates the DB storage path. |
| fs.mounts.path | /data | Where Postgres writes inside enclave. |
| fs.mounts.uri | file:/var/lib/encrypted\_db | Where encrypted blobs live on host. |
| sgx.max\_threads | 64 | Postgres requires many threads/processes. |

### **8.3 The "Self-Sovereign" Bootstrapping Flow**

To ensure the operator *never* sees the secrets:

1. **Operator Action:** Starts the Gramine enclave. The application halts, waiting for a key.  
2. **Attestation:** The agent generates an SGX Quote and sends it to the Owner (running a local client).  
3. **Verification:** The Owner verifies the Quote matches the expected MRENCLAVE of the open-source code.  
4. **Provisioning:** The Owner sends the File System Encryption Key (wrapped with the enclave's public key) to the agent.  
5. **Unlock:** The agent unwraps the key, mounts the encrypted /data directory, and starts PostgreSQL. The database is now live, but its memory and disk storage are cryptographically inaccessible to the operator.

## **9\. Conclusion**

The technology to run a "black box" autonomous agent is no longer theoretical. **Intel SGX with Gramine** offers the most mature, open-source, and self-hostable path for running stateful Python and PostgreSQL workloads with transparent memory and disk encryption. **AWS Nitro Enclaves** offer superior isolation for stateless or ephemeral processing but require significant re-engineering for persistent databases. **AMD SEV-SNP** provides the easiest migration path ("lift and shift") but entails a larger trust boundary involving the guest OS. For those seeking a decentralized approach, **Oasis ROFL** presents a compelling vision of "serverless TEEs" that abstract the infrastructure entirely.

By adopting these architectures, developers can deploy AI agents that possess genuine autonomy—owning their secrets, protecting their memories, and serving their users without exposing their internal state to the infrastructure that powers them.

## **10\. Comparative Summary of Technologies**

| Feature | Intel SGX (Gramine) | AWS Nitro Enclaves | AMD SEV-SNP | Oasis ROFL |
| :---- | :---- | :---- | :---- | :---- |
| **Isolation Unit** | Process (Enclave) | VM (Cut from Parent) | Virtual Machine | Container in TEE |
| **Unmodified Postgres** | **Yes** (via LibOS) | Difficult (No Storage) | **Yes** (Native OS) | Yes (Container) |
| **Persistence** | **Encrypted FS** (Transparent) | Manual (via VSOCK) | Full Disk Encryption | Chain/Storage Nodes |
| **Self-Hostable** | **Yes** (Linux \+ Driver) | No (AWS Proprietary) | **Yes** (KVM/QEMU) | No (Network) |
| **Open Source** | **Yes** (Gramine) | Tools Only (CLI) | **Yes** (Kernel/QEMU) | **Yes** (SDK/Core) |
| **Attestation** | DCAP (Self-Verifiable) | AWS Signed Document | PSP Signed Report | Network Consensus |
| **Operator Access** | Blocked by CPU | Blocked by Hypervisor | Blocked by CPU | Blocked by TEE |

#### **Works cited**

1. Secure Enclaves \- BlindAI, accessed December 27, 2025, [https://blindai.mithrilsecurity.io/en/latest/docs/concepts/SGX\_vs\_Nitro/](https://blindai.mithrilsecurity.io/en/latest/docs/concepts/SGX_vs_Nitro/)  
2. Comparative Review of AWS and Azure Confidential Computing ..., accessed December 27, 2025, [https://jisem-journal.com/index.php/journal/article/download/1805/695/2908](https://jisem-journal.com/index.php/journal/article/download/1805/695/2908)  
3. Secure enclaves | Edgeless Systems wiki, accessed December 27, 2025, [https://www.edgeless.systems/wiki/what-is-confidential-computing/secure-enclaves](https://www.edgeless.systems/wiki/what-is-confidential-computing/secure-enclaves)  
4. README.md \- flashbots/geth-sgx-gramine \- GitHub, accessed December 27, 2025, [https://github.com/flashbots/geth-sgx-gramine/blob/main/README.md](https://github.com/flashbots/geth-sgx-gramine/blob/main/README.md)  
5. Running Geth within SGX: Our Experience, Learnings and Code, accessed December 27, 2025, [https://writings.flashbots.net/geth-inside-sgx](https://writings.flashbots.net/geth-inside-sgx)  
6. Gramine: Protecting Unmodified Linux Applications with Confidential ..., accessed December 27, 2025, [https://cdrdv2-public.intel.com/738673/gramine-solution-brief.pdf](https://cdrdv2-public.intel.com/738673/gramine-solution-brief.pdf)  
7. Gramine features, accessed December 27, 2025, [https://gramine.readthedocs.io/en/stable/devel/features.html](https://gramine.readthedocs.io/en/stable/devel/features.html)  
8. AMD Secure Encrypted Virtualization (SEV), accessed December 27, 2025, [https://www.amd.com/en/developer/sev.html](https://www.amd.com/en/developer/sev.html)  
9. End-to-End Confidentiality with SEV-SNP Leveraging In-Memory ..., accessed December 27, 2025, [https://systex-workshop.github.io/2025/papers/systex25-final82.pdf](https://systex-workshop.github.io/2025/papers/systex25-final82.pdf)  
10. Running Python App on AWS Nitro Enclaves \- DEV Community, accessed December 27, 2025, [https://dev.to/aws-builders/running-python-app-on-aws-nitro-enclaves-3lhp](https://dev.to/aws-builders/running-python-app-on-aws-nitro-enclaves-3lhp)  
11. Nitro Enclaves application development on Linux instances, accessed December 27, 2025, [https://docs.aws.amazon.com/enclaves/latest/user/developing-applications-linux.html](https://docs.aws.amazon.com/enclaves/latest/user/developing-applications-linux.html)  
12. AWS Nitro File Persistence, accessed December 27, 2025, [https://support.fortanix.com/docs/users-guide-aws-nitro-file-persistence](https://support.fortanix.com/docs/users-guide-aws-nitro-file-persistence)  
13. AWS Nitro Enclaves, accessed December 27, 2025, [https://aws.amazon.com/ec2/nitro/nitro-enclaves/](https://aws.amazon.com/ec2/nitro/nitro-enclaves/)  
14. Encrypted Files in Gramine, accessed December 27, 2025, [https://gramine.readthedocs.io/en/stable/devel/encfiles.html](https://gramine.readthedocs.io/en/stable/devel/encfiles.html)  
15. Intel SGX programming model challenges and how Gramine OSS ..., accessed December 27, 2025, [https://techcommunity.microsoft.com/blog/azureconfidentialcomputingblog/developers-guide-to-gramine-open-source-lib-os-for-running-unmodified-linux-apps/3645841](https://techcommunity.microsoft.com/blog/azureconfidentialcomputingblog/developers-guide-to-gramine-open-source-lib-os-for-running-unmodified-linux-apps/3645841)  
16. Why LibOS for SGX? — Confidential Computing Zoo documentation, accessed December 27, 2025, [https://cczoo.readthedocs.io/en/latest/LibOS/libos.html](https://cczoo.readthedocs.io/en/latest/LibOS/libos.html)  
17. Why LibOS for SGX? \- GitHub, accessed December 27, 2025, [https://github.com/intel/confidential-computing-zoo/blob/main/documents/readthedoc/docs/source/LibOS/libos.md](https://github.com/intel/confidential-computing-zoo/blob/main/documents/readthedoc/docs/source/LibOS/libos.md)  
18. Securing our software supply-chain better with reproducible builds ..., accessed December 27, 2025, [https://monzo.com/blog/securing-our-software-supply-chain-better-with-reproducible-builds-for](https://monzo.com/blog/securing-our-software-supply-chain-better-with-reproducible-builds-for)  
19. Utilities to reproducibly build images for AWS Nitro Enclaves \- GitHub, accessed December 27, 2025, [https://github.com/monzo/aws-nitro-util](https://github.com/monzo/aws-nitro-util)  
20. Gramine Integration \- Intel® Trust Authority, accessed December 27, 2025, [https://docs.trustauthority.intel.com/main/articles/articles/ita/integrate-gramine.html](https://docs.trustauthority.intel.com/main/articles/articles/ita/integrate-gramine.html)  
21. confidential-computing.tee.dcap/QuoteGeneration/README.md at ..., accessed December 27, 2025, [https://github.com/intel/confidential-computing.tee.dcap/blob/main/QuoteGeneration/README.md](https://github.com/intel/confidential-computing.tee.dcap/blob/main/QuoteGeneration/README.md)  
22. sgx-dcap-quote-verify-python \- PyPI, accessed December 27, 2025, [https://pypi.org/project/sgx-dcap-quote-verify-python/](https://pypi.org/project/sgx-dcap-quote-verify-python/)  
23. intel/confidential-computing.tee.dcap \- GitHub, accessed December 27, 2025, [https://github.com/intel/confidential-computing.tee.dcap](https://github.com/intel/confidential-computing.tee.dcap)  
24. Validating attestation documents produced by AWS Nitro Enclaves, accessed December 27, 2025, [https://aws.amazon.com/blogs/compute/validating-attestation-documents-produced-by-aws-nitro-enclaves/](https://aws.amazon.com/blogs/compute/validating-attestation-documents-produced-by-aws-nitro-enclaves/)  
25. How to Use AWS Nitro Enclaves Attestation Document, accessed December 27, 2025, [https://dev.to/aws-builders/how-to-use-aws-nitro-enclaves-attestation-document-2376](https://dev.to/aws-builders/how-to-use-aws-nitro-enclaves-attestation-document-2376)  
26. Cryptographic attestation \- AWS Nitro Enclaves, accessed December 27, 2025, [https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html](https://docs.aws.amazon.com/enclaves/latest/user/set-up-attestation.html)  
27. PostgreSQL Fully Homomorphic Encryption \- GitHub, accessed December 27, 2025, [https://github.com/FHE-Postgres/pg\_fhe](https://github.com/FHE-Postgres/pg_fhe)  
28. Homomorphic Encryption for Confidential Statistical Computation, accessed December 27, 2025, [https://www.mdpi.com/2624-800X/6/1/4](https://www.mdpi.com/2624-800X/6/1/4)  
29. Exploring the Feasibility of Fully Homomorphic Encryption, accessed December 27, 2025, [https://www.researchgate.net/publication/272393662\_Exploring\_the\_Feasibility\_of\_Fully\_Homomorphic\_Encryption](https://www.researchgate.net/publication/272393662_Exploring_the_Feasibility_of_Fully_Homomorphic_Encryption)  
30. Characterizing and Protecting Multi-Agent Computation, accessed December 27, 2025, [https://ncr.mae.ufl.edu/aa/files/Fall2022/FedeleF2022.pdf](https://ncr.mae.ufl.edu/aa/files/Fall2022/FedeleF2022.pdf)  
31. AutoMPC: Efficient Multi-Party Computation for Secure and Privacy ..., accessed December 27, 2025, [https://ceur-ws.org/Vol-2301/paper\_13.pdf](https://ceur-ws.org/Vol-2301/paper_13.pdf)  
32. Stateful Abstractions of Secure Multiparty Computation, accessed December 27, 2025, [https://www.researchgate.net/publication/282681268\_Stateful\_abstractions\_of\_secure\_multiparty\_computation](https://www.researchgate.net/publication/282681268_Stateful_abstractions_of_secure_multiparty_computation)  
33. Runtime Off-Chain Logic (ROFL) | Oasis Documentation, accessed December 27, 2025, [https://docs.oasis.io/build/rofl/](https://docs.oasis.io/build/rofl/)  
34. A Deep Technical Dive into Oasis Protocol's Runtime Offchain Logic ..., accessed December 27, 2025, [https://medium.com/@caerlower/inside-rofl-a-deep-technical-dive-into-oasis-protocols-runtime-offchain-logic-framework-330c9c97559e](https://medium.com/@caerlower/inside-rofl-a-deep-technical-dive-into-oasis-protocols-runtime-offchain-logic-framework-330c9c97559e)  
35. ROFL | Oasis Documentation, accessed December 27, 2025, [https://docs.oasis.io/general/manage-tokens/cli/rofl/](https://docs.oasis.io/general/manage-tokens/cli/rofl/)  
36. Breaking the Limits: How Oasis Protocol's ROFL Framework Is ..., accessed December 27, 2025, [https://medium.com/@caerlower/breaking-the-limits-how-oasis-protocols-rofl-framework-is-expanding-what-s-possible-in-web3-8f3c8e2ef630](https://medium.com/@caerlower/breaking-the-limits-how-oasis-protocols-rofl-framework-is-expanding-what-s-possible-in-web3-8f3c8e2ef630)  
37. Secret Network brings decentralized confidential computing (DeCC ..., accessed December 27, 2025, [https://scrt.network/confidential-computing-layer](https://scrt.network/confidential-computing-layer)  
38. jeugregg/secret\_pass\_manager: Password manager using Secret ..., accessed December 27, 2025, [https://github.com/jeugregg/secret\_pass\_manager](https://github.com/jeugregg/secret_pass_manager)  
39. PostgreSQL with Gramine \- Google Groups, accessed December 27, 2025, [https://groups.google.com/g/gramine-users/c/pI\_SsOFPqSw](https://groups.google.com/g/gramine-users/c/pI_SsOFPqSw)