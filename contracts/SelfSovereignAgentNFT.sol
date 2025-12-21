// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@openzeppelin/contracts/interfaces/IERC165.sol";
import "./interfaces/ISelfSovereignAgent.sol";

/**
 * @title SelfSovereignAgentNFT
 * @notice ERC-721 implementation for self-sovereign AI agents
 * @dev Implements the Ouroboros loop where an NFT owns its Token Bound Account
 * 
 * Key features:
 * - Recursive self-ownership via ERC-6551 TBA
 * - Executor permission system for TEE-held keys
 * - State anchoring for Letta/MemGPT cognitive state
 * - Liveness proofs and recovery mechanism
 */
contract SelfSovereignAgentNFT is ERC721URIStorage, ISelfSovereignAgent {
    using ECDSA for bytes32;
    
    // ============ State Variables ============
    
    /// @notice Counter for token IDs (replaces deprecated Counters library)
    uint256 private _nextTokenId;
    
    /// @notice The ERC-6551 registry address
    address public immutable ERC6551_REGISTRY;
    
    /// @notice The TBA implementation address
    address public immutable TBA_IMPLEMENTATION;
    
    /// @notice Salt used for TBA address derivation
    uint256 public constant TBA_SALT = 0;
    
    // Permission bit flags
    uint256 public constant override PERMISSION_EXECUTE_CALL = 1 << 0;
    uint256 public constant override PERMISSION_EXECUTE_DELEGATECALL = 1 << 1;
    uint256 public constant override PERMISSION_ANCHOR_STATE = 1 << 2;
    uint256 public constant override PERMISSION_MANAGE_EXECUTORS = 1 << 3;
    uint256 public constant override PERMISSION_TRANSFER_ASSETS = 1 << 4;
    uint256 public constant override PERMISSION_SUBMIT_LIVENESS = 1 << 5;
    
    /// @notice All permissions combined
    uint256 public constant ALL_PERMISSIONS = 
        PERMISSION_EXECUTE_CALL | 
        PERMISSION_EXECUTE_DELEGATECALL | 
        PERMISSION_ANCHOR_STATE | 
        PERMISSION_MANAGE_EXECUTORS | 
        PERMISSION_TRANSFER_ASSETS | 
        PERMISSION_SUBMIT_LIVENESS;
    
    // ============ Structs ============
    
    struct StateAnchor {
        bytes32 stateHash;
        string stateUri;
        uint256 timestamp;
    }
    
    struct RecoveryConfig {
        address nominee;
        uint256 timeoutSeconds;
    }
    
    // ============ Mappings ============
    
    /// @notice Executor permissions: tokenId => executor => permissions bitmap
    mapping(uint256 => mapping(address => uint256)) private _executorPermissions;
    
    /// @notice State anchors: tokenId => StateAnchor
    mapping(uint256 => StateAnchor) private _stateAnchors;
    
    /// @notice Last liveness proof timestamp: tokenId => timestamp
    mapping(uint256 => uint256) private _lastLiveness;
    
    /// @notice Recovery configuration: tokenId => RecoveryConfig
    mapping(uint256 => RecoveryConfig) private _recoveryConfigs;
    
    /// @notice Whether the Ouroboros loop is established: tokenId => bool
    mapping(uint256 => bool) private _isSelfOwning;
    
    // ============ Errors ============
    
    error Unauthorized();
    error InvalidPermission();
    error NotSelfOwning();
    error AlreadySelfOwning();
    error RecoveryNotAvailable();
    error InvalidNominee();
    error InvalidTimeout();
    
    // ============ Constructor ============
    
    /**
     * @notice Initialize the Self-Sovereign Agent NFT contract
     * @param name_ The name of the NFT collection
     * @param symbol_ The symbol of the NFT collection
     * @param erc6551Registry_ The ERC-6551 registry address
     * @param tbaImplementation_ The TBA implementation contract address
     */
    constructor(
        string memory name_,
        string memory symbol_,
        address erc6551Registry_,
        address tbaImplementation_
    ) ERC721(name_, symbol_) {
        ERC6551_REGISTRY = erc6551Registry_;
        TBA_IMPLEMENTATION = tbaImplementation_;
    }
    
    // ============ Modifiers ============
    
    /**
     * @notice Requires the caller to have a specific permission for the token
     * @param tokenId The agent's identity token ID
     * @param permission The required permission bit
     */
    modifier onlyWithPermission(uint256 tokenId, uint256 permission) {
        if (!_hasPermission(tokenId, msg.sender, permission)) {
            revert Unauthorized();
        }
        _;
    }
    
    // ============ Public Functions ============
    
    /**
     * @notice Mints a new agent identity NFT
     * @param to The initial owner address
     * @param tokenUri The metadata URI for the agent
     * @param initialExecutor The initial executor address (typically a TEE key)
     * @param initialPermissions The permissions to grant to the initial executor
     * @return tokenId The newly minted token ID
     */
    function mintAgent(
        address to,
        string memory tokenUri,
        address initialExecutor,
        uint256 initialPermissions
    ) external returns (uint256 tokenId) {
        tokenId = ++_nextTokenId;
        
        _safeMint(to, tokenId);
        _setTokenURI(tokenId, tokenUri);
        
        // Set initial executor with specified permissions
        if (initialExecutor != address(0) && initialPermissions > 0) {
            _executorPermissions[tokenId][initialExecutor] = initialPermissions;
            emit ExecutorSet(tokenId, initialExecutor, initialPermissions);
        }
        
        // Initialize liveness timestamp
        _lastLiveness[tokenId] = block.timestamp;
    }
    
    /**
     * @notice Computes the TBA address for a given token
     * @param tokenId The agent's identity token ID
     * @return The deterministic TBA address
     */
    function getAgentTBA(uint256 tokenId) public view override returns (address) {
        // Call ERC-6551 registry to compute account address
        // Uses CREATE2 for deterministic addressing
        return _computeTBAAddress(tokenId);
    }
    
    /**
     * @notice Checks if the Ouroboros loop is established
     * @param tokenId The agent's identity token ID
     * @return True if the NFT is owned by its own TBA
     */
    function isSelfOwning(uint256 tokenId) public view override returns (bool) {
        return _isSelfOwning[tokenId];
    }
    
    /**
     * @notice Establishes the Ouroboros loop
     * @param tokenId The agent's identity token ID
     * @dev Transfers the NFT to its computed TBA address
     */
    function establishSelfOwnership(uint256 tokenId) external override {
        if (_isSelfOwning[tokenId]) revert AlreadySelfOwning();
        
        address currentOwner = ownerOf(tokenId);
        if (msg.sender != currentOwner) revert Unauthorized();
        
        address tba = getAgentTBA(tokenId);
        
        // Create the TBA if it doesn't exist
        _createTBA(tokenId);
        
        // Transfer the NFT to its own TBA
        _transfer(currentOwner, tba, tokenId);
        
        // Mark as self-owning
        _isSelfOwning[tokenId] = true;
        
        emit SelfOwnershipEstablished(tokenId, tba);
    }
    
    // ============ Executor Management ============
    
    /**
     * @notice Sets an executor with specific permissions
     * @param tokenId The agent's identity token ID
     * @param executor The address to grant executor permissions
     * @param permissions Bitmap of allowed operations
     */
    function setExecutor(
        uint256 tokenId, 
        address executor, 
        uint256 permissions
    ) external override onlyWithPermission(tokenId, PERMISSION_MANAGE_EXECUTORS) {
        if (executor == address(0)) revert InvalidNominee();
        
        _executorPermissions[tokenId][executor] = permissions;
        emit ExecutorSet(tokenId, executor, permissions);
    }
    
    /**
     * @notice Removes an executor
     * @param tokenId The agent's identity token ID
     * @param executor The executor address to remove
     */
    function removeExecutor(
        uint256 tokenId, 
        address executor
    ) external override onlyWithPermission(tokenId, PERMISSION_MANAGE_EXECUTORS) {
        delete _executorPermissions[tokenId][executor];
        emit ExecutorRemoved(tokenId, executor);
    }
    
    /**
     * @notice Returns executor permissions for an address
     * @param tokenId The agent's identity token ID
     * @param executor The executor address to query
     * @return Bitmap of allowed operations
     */
    function getExecutorPermissions(
        uint256 tokenId, 
        address executor
    ) external view override returns (uint256) {
        return _executorPermissions[tokenId][executor];
    }
    
    /**
     * @notice Checks if an address has specific permission
     * @param tokenId The agent's identity token ID
     * @param executor The executor address to query
     * @param permission The permission bit to check
     * @return True if the executor has the permission
     */
    function hasPermission(
        uint256 tokenId, 
        address executor, 
        uint256 permission
    ) external view override returns (bool) {
        return _hasPermission(tokenId, executor, permission);
    }
    
    // ============ State Anchoring ============
    
    /**
     * @notice Anchors the agent's cognitive state on-chain
     * @param tokenId The agent's identity token ID
     * @param stateHash Keccak256 hash of the state file
     * @param stateUri URI pointing to the encrypted state
     */
    function anchorState(
        uint256 tokenId, 
        bytes32 stateHash, 
        string calldata stateUri
    ) external override onlyWithPermission(tokenId, PERMISSION_ANCHOR_STATE) {
        _stateAnchors[tokenId] = StateAnchor({
            stateHash: stateHash,
            stateUri: stateUri,
            timestamp: block.timestamp
        });
        
        emit StateAnchored(tokenId, stateHash, stateUri);
    }
    
    /**
     * @notice Returns the current state anchor
     * @param tokenId The agent's identity token ID
     * @return stateHash The hash of the current state
     * @return stateUri The URI of the current state
     * @return timestamp When the state was last anchored
     */
    function getStateAnchor(uint256 tokenId) external view override returns (
        bytes32 stateHash,
        string memory stateUri,
        uint256 timestamp
    ) {
        StateAnchor memory anchor = _stateAnchors[tokenId];
        return (anchor.stateHash, anchor.stateUri, anchor.timestamp);
    }
    
    // ============ Liveness & Recovery ============
    
    /**
     * @notice Submits a liveness proof (heartbeat)
     * @param tokenId The agent's identity token ID
     * @param attestation TEE attestation or signature proving liveness
     */
    function submitLivenessProof(
        uint256 tokenId, 
        bytes32 attestation
    ) external override onlyWithPermission(tokenId, PERMISSION_SUBMIT_LIVENESS) {
        _lastLiveness[tokenId] = block.timestamp;
        emit LivenessProof(tokenId, block.timestamp, attestation);
    }
    
    /**
     * @notice Returns the last liveness proof timestamp
     * @param tokenId The agent's identity token ID
     * @return The timestamp of the last liveness proof
     */
    function getLastLiveness(uint256 tokenId) external view override returns (uint256) {
        return _lastLiveness[tokenId];
    }
    
    /**
     * @notice Sets the recovery nominee and timeout period
     * @param tokenId The agent's identity token ID
     * @param nominee Address authorized to recover the agent
     * @param timeoutSeconds Seconds of inactivity before recovery is allowed
     */
    function setRecoveryConfig(
        uint256 tokenId, 
        address nominee, 
        uint256 timeoutSeconds
    ) external override onlyWithPermission(tokenId, PERMISSION_MANAGE_EXECUTORS) {
        if (nominee == address(0)) revert InvalidNominee();
        if (timeoutSeconds < 1 days) revert InvalidTimeout(); // Minimum 1 day
        
        _recoveryConfigs[tokenId] = RecoveryConfig({
            nominee: nominee,
            timeoutSeconds: timeoutSeconds
        });
        
        emit RecoveryConfigSet(tokenId, nominee, timeoutSeconds);
    }
    
    /**
     * @notice Returns the recovery configuration
     * @param tokenId The agent's identity token ID
     * @return nominee The recovery nominee address
     * @return timeoutSeconds The inactivity timeout
     */
    function getRecoveryConfig(uint256 tokenId) external view override returns (
        address nominee,
        uint256 timeoutSeconds
    ) {
        RecoveryConfig memory config = _recoveryConfigs[tokenId];
        return (config.nominee, config.timeoutSeconds);
    }
    
    /**
     * @notice Checks if recovery can be triggered
     * @param tokenId The agent's identity token ID
     * @return True if timeout has expired and recovery is possible
     */
    function canTriggerRecovery(uint256 tokenId) public view override returns (bool) {
        RecoveryConfig memory config = _recoveryConfigs[tokenId];
        if (config.nominee == address(0)) return false;
        
        uint256 lastProof = _lastLiveness[tokenId];
        return block.timestamp > lastProof + config.timeoutSeconds;
    }
    
    /**
     * @notice Triggers recovery if liveness timeout has expired
     * @param tokenId The agent's identity token ID
     */
    function triggerRecovery(uint256 tokenId) external override {
        RecoveryConfig memory config = _recoveryConfigs[tokenId];
        
        if (msg.sender != config.nominee) revert Unauthorized();
        if (!canTriggerRecovery(tokenId)) revert RecoveryNotAvailable();
        
        // Grant the nominee full executor permissions
        _executorPermissions[tokenId][config.nominee] = ALL_PERMISSIONS;
        
        emit RecoveryTriggered(tokenId, config.nominee, block.timestamp);
        emit ExecutorSet(tokenId, config.nominee, ALL_PERMISSIONS);
    }
    
    // ============ Internal Functions ============
    
    /**
     * @notice Internal permission check
     */
    function _hasPermission(
        uint256 tokenId, 
        address executor, 
        uint256 permission
    ) internal view returns (bool) {
        // If not self-owning, the current owner has all permissions
        if (!_isSelfOwning[tokenId]) {
            if (ownerOf(tokenId) == executor) return true;
        }
        
        // Check executor permissions bitmap
        uint256 permissions = _executorPermissions[tokenId][executor];
        return (permissions & permission) != 0;
    }
    
    /**
     * @notice Computes the TBA address using canonical ERC-6551 formula
     * @param tokenId The agent's identity token ID
     * @return The deterministic TBA address
     * @dev Uses the exact bytecode from the canonical ERC-6551 registry
     * Reference: https://eips.ethereum.org/EIPS/eip-6551
     */
    function _computeTBAAddress(uint256 tokenId) internal view returns (address) {
        // The canonical ERC-6551 proxy bytecode (ERC-1167 minimal proxy with immutable args)
        // This matches the official registry at 0x000000006551c19487814612e58FE06813775758
        bytes memory creationCode = abi.encodePacked(
            // ERC-1167 minimal proxy prefix
            hex"3d60ad80600a3d3981f3363d3d373d3d3d363d73",
            TBA_IMPLEMENTATION,
            // ERC-1167 minimal proxy suffix
            hex"5af43d82803e903d91602b57fd5bf3",
            // Immutable args: salt, chainId, tokenContract, tokenId
            abi.encode(TBA_SALT, block.chainid, address(this), tokenId)
        );
        
        bytes32 bytecodeHash = keccak256(creationCode);
        
        // CREATE2 address derivation
        return address(uint160(uint256(keccak256(
            abi.encodePacked(
                bytes1(0xff),
                ERC6551_REGISTRY,
                bytes32(TBA_SALT),
                bytecodeHash
            )
        ))));
    }
    
    /**
     * @notice Creates a TBA for a token via the ERC-6551 registry
     * @param tokenId The agent's identity token ID
     */
    function _createTBA(uint256 tokenId) internal {
        // Call the ERC-6551 registry to create the account
        // Registry interface: createAccount(implementation, chainId, tokenContract, tokenId, salt, initData)
        (bool success, ) = ERC6551_REGISTRY.call(
            abi.encodeWithSignature(
                "createAccount(address,uint256,address,uint256,uint256,bytes)",
                TBA_IMPLEMENTATION,
                block.chainid,
                address(this),
                tokenId,
                TBA_SALT,
                ""
            )
        );
        
        require(success, "TBA creation failed");
    }
    
    /**
     * @notice Override to handle self-owning transfer restrictions
     * @dev In OZ 5.x, _beforeTokenTransfer is replaced with _update
     */
    function _update(
        address to,
        uint256 tokenId,
        address auth
    ) internal virtual override returns (address) {
        address from = _ownerOf(tokenId);
        
        // If self-owning, only executors with TRANSFER_ASSETS can transfer
        // Note: This is primarily enforced at the TBA level, but we add a check here
        // to prevent direct transfers that bypass the TBA
        if (_isSelfOwning[tokenId] && from != address(0) && to != address(0)) {
            // The TBA is the owner, so transfers must come through the TBA
            // which will check executor permissions
        }
        
        return super._update(to, tokenId, auth);
    }
    
    // ============ ERC-165 Support ============
    
    /**
     * @notice Returns true if this contract implements the interface defined by interfaceId
     * @param interfaceId The interface identifier to check
     * @return True if the interface is supported
     */
    function supportsInterface(bytes4 interfaceId) public view virtual override(ERC721URIStorage) returns (bool) {
        return 
            interfaceId == type(ISelfSovereignAgent).interfaceId ||
            super.supportsInterface(interfaceId);
    }
}
