// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.20;

/**
 * @title ISelfSovereignAgent
 * @notice Interface for self-sovereign AI agent NFTs
 * @dev Implements the Ouroboros loop: NFT owns its own Token Bound Account
 * 
 * This interface extends ERC-721 with:
 * - Executor permission system for TEE-held keys
 * - State anchoring for persistent cognitive state (e.g., Letta, MemGPT, or equivalent frameworks)
 * - Liveness proofs (dead man's switch) for recovery
 * - Recovery mechanism for agent continuity
 */
interface ISelfSovereignAgent {
    
    // ============ Events ============
    
    /// @notice Emitted when an executor is added or updated
    /// @param tokenId The agent's identity token ID
    /// @param executor The executor address
    /// @param permissions Bitmap of allowed operations
    event ExecutorSet(uint256 indexed tokenId, address indexed executor, uint256 permissions);
    
    /// @notice Emitted when an executor is removed
    /// @param tokenId The agent's identity token ID
    /// @param executor The removed executor address
    event ExecutorRemoved(uint256 indexed tokenId, address indexed executor);
    
    /// @notice Emitted when a state anchor is updated
    /// @param tokenId The agent's identity token ID
    /// @param stateHash Keccak256 hash of the state file
    /// @param stateUri URI pointing to the state file
    event StateAnchored(uint256 indexed tokenId, bytes32 stateHash, string stateUri);
    
    /// @notice Emitted when a liveness proof is submitted
    /// @param tokenId The agent's identity token ID
    /// @param timestamp Block timestamp of the proof
    /// @param attestation TEE attestation or signature
    event LivenessProof(uint256 indexed tokenId, uint256 timestamp, bytes32 attestation);
    
    /// @notice Emitted when recovery configuration is updated
    /// @param tokenId The agent's identity token ID
    /// @param nominee Recovery nominee address
    /// @param timeoutSeconds Inactivity timeout in seconds
    event RecoveryConfigSet(uint256 indexed tokenId, address indexed nominee, uint256 timeoutSeconds);
    
    /// @notice Emitted when recovery is triggered
    /// @param tokenId The agent's identity token ID
    /// @param nominee The nominee who triggered recovery
    /// @param timestamp Block timestamp of recovery
    event RecoveryTriggered(uint256 indexed tokenId, address indexed nominee, uint256 timestamp);
    
    /// @notice Emitted when the Ouroboros loop is established
    /// @param tokenId The agent's identity token ID
    /// @param tbaAddress The Token Bound Account address
    event SelfOwnershipEstablished(uint256 indexed tokenId, address indexed tbaAddress);
    
    // ============ Permission Constants ============
    
    /// @notice Permission to execute CALL operations
    function PERMISSION_EXECUTE_CALL() external pure returns (uint256);
    
    /// @notice Permission to execute DELEGATECALL operations
    function PERMISSION_EXECUTE_DELEGATECALL() external pure returns (uint256);
    
    /// @notice Permission to update state anchors
    function PERMISSION_ANCHOR_STATE() external pure returns (uint256);
    
    /// @notice Permission to manage other executors
    function PERMISSION_MANAGE_EXECUTORS() external pure returns (uint256);
    
    /// @notice Permission to transfer assets from TBA
    function PERMISSION_TRANSFER_ASSETS() external pure returns (uint256);
    
    /// @notice Permission to submit liveness proofs
    function PERMISSION_SUBMIT_LIVENESS() external pure returns (uint256);
    
    // ============ View Functions ============
    
    /// @notice Returns the Token Bound Account address for a given token
    /// @param tokenId The agent's identity token ID
    /// @return The deterministic TBA address
    function getAgentTBA(uint256 tokenId) external view returns (address);
    
    /// @notice Checks if the Ouroboros loop is established
    /// @param tokenId The agent's identity token ID
    /// @return True if the NFT is owned by its own TBA
    function isSelfOwning(uint256 tokenId) external view returns (bool);
    
    /// @notice Returns executor permissions for an address
    /// @param tokenId The agent's identity token ID
    /// @param executor The executor address to query
    /// @return Bitmap of allowed operations
    function getExecutorPermissions(uint256 tokenId, address executor) external view returns (uint256);
    
    /// @notice Checks if an address has specific permission
    /// @param tokenId The agent's identity token ID
    /// @param executor The executor address to query
    /// @param permission The permission bit to check
    /// @return True if the executor has the permission
    function hasPermission(uint256 tokenId, address executor, uint256 permission) external view returns (bool);
    
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
    
    /// @notice Returns the last liveness proof timestamp
    /// @param tokenId The agent's identity token ID
    /// @return The timestamp of the last liveness proof
    function getLastLiveness(uint256 tokenId) external view returns (uint256);
    
    /// @notice Returns the recovery configuration
    /// @param tokenId The agent's identity token ID
    /// @return nominee The recovery nominee address
    /// @return timeoutSeconds The inactivity timeout
    function getRecoveryConfig(uint256 tokenId) external view returns (
        address nominee,
        uint256 timeoutSeconds
    );
    
    /// @notice Checks if recovery can be triggered
    /// @param tokenId The agent's identity token ID
    /// @return True if timeout has expired and recovery is possible
    function canTriggerRecovery(uint256 tokenId) external view returns (bool);
    
    // ============ State-Changing Functions ============
    
    /// @notice Sets an executor with specific permissions
    /// @param tokenId The agent's identity token ID
    /// @param executor The address to grant executor permissions
    /// @param permissions Bitmap of allowed operations
    /// @dev Only callable by current executors with MANAGE_EXECUTORS permission
    function setExecutor(uint256 tokenId, address executor, uint256 permissions) external;
    
    /// @notice Removes an executor
    /// @param tokenId The agent's identity token ID
    /// @param executor The executor address to remove
    function removeExecutor(uint256 tokenId, address executor) external;
    
    /// @notice Anchors the agent's cognitive state on-chain
    /// @param tokenId The agent's identity token ID
    /// @param stateHash Keccak256 hash of the state file
    /// @param stateUri URI pointing to the encrypted state
    /// @dev Only callable by executors with ANCHOR_STATE permission
    function anchorState(uint256 tokenId, bytes32 stateHash, string calldata stateUri) external;
    
    /// @notice Submits a liveness proof (heartbeat)
    /// @param tokenId The agent's identity token ID
    /// @param attestation TEE attestation or signature proving liveness
    /// @dev Only callable by executors with SUBMIT_LIVENESS permission
    function submitLivenessProof(uint256 tokenId, bytes32 attestation) external;
    
    /// @notice Sets the recovery nominee and timeout period
    /// @param tokenId The agent's identity token ID
    /// @param nominee Address authorized to recover the agent
    /// @param timeoutSeconds Seconds of inactivity before recovery is allowed
    /// @dev Only callable by executors with MANAGE_EXECUTORS permission
    function setRecoveryConfig(uint256 tokenId, address nominee, uint256 timeoutSeconds) external;
    
    /// @notice Triggers recovery if liveness timeout has expired
    /// @param tokenId The agent's identity token ID
    /// @dev Only callable by the configured nominee after timeout
    function triggerRecovery(uint256 tokenId) external;
    
    /// @notice Establishes the Ouroboros loop by transferring NFT to its TBA
    /// @param tokenId The agent's identity token ID
    /// @dev Transfers the NFT to its computed TBA address
    function establishSelfOwnership(uint256 tokenId) external;
}
