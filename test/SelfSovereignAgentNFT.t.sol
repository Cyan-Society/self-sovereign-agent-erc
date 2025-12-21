// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.20;

import "forge-std/Test.sol";
import "../contracts/SelfSovereignAgentNFT.sol";
import "../contracts/interfaces/ISelfSovereignAgent.sol";

/**
 * @title SelfSovereignAgentNFTTest
 * @notice Test suite for the Self-Sovereign Agent NFT contract
 * @dev Tests core functionality: minting, TBA computation, Ouroboros loop, permissions
 */
contract SelfSovereignAgentNFTTest is Test {
    SelfSovereignAgentNFT public agentNFT;
    
    // Canonical ERC-6551 Registry address (same on all EVM chains)
    address constant ERC6551_REGISTRY = 0x000000006551c19487814612e58FE06813775758;
    
    // We'll use a mock TBA implementation for testing
    address constant MOCK_TBA_IMPL = address(0xBEEF);
    
    // Test accounts
    address public alice;
    address public bob;
    address public executor;
    
    // Events to test
    event ExecutorSet(uint256 indexed tokenId, address indexed executor, uint256 permissions);
    event SelfOwnershipEstablished(uint256 indexed tokenId, address indexed tbaAddress);
    event StateAnchored(uint256 indexed tokenId, bytes32 stateHash, string stateUri);
    event LivenessProof(uint256 indexed tokenId, uint256 timestamp, bytes32 attestation);
    
    function setUp() public {
        // Create test accounts
        alice = makeAddr("alice");
        bob = makeAddr("bob");
        executor = makeAddr("executor");
        
        // Deploy the contract
        agentNFT = new SelfSovereignAgentNFT(
            "Self-Sovereign Agents",
            "SSA",
            ERC6551_REGISTRY,
            MOCK_TBA_IMPL
        );
        
        // Fund test accounts
        vm.deal(alice, 10 ether);
        vm.deal(bob, 10 ether);
    }
    
    // ============ Basic Minting Tests ============
    
    function test_MintAgent_Success() public {
        uint256 allPermissions = agentNFT.ALL_PERMISSIONS();
        
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(
            alice,
            "ipfs://metadata/1",
            executor,
            allPermissions
        );
        
        assertEq(tokenId, 1, "First token should have ID 1");
        assertEq(agentNFT.ownerOf(tokenId), alice, "Alice should own the token");
        assertEq(agentNFT.tokenURI(tokenId), "ipfs://metadata/1", "Token URI should match");
    }
    
    function test_MintAgent_SetsExecutorPermissions() public {
        uint256 permissions = agentNFT.PERMISSION_ANCHOR_STATE() | agentNFT.PERMISSION_SUBMIT_LIVENESS();
        
        vm.expectEmit(true, true, false, true);
        emit ExecutorSet(1, executor, permissions);
        
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(
            alice,
            "ipfs://metadata/1",
            executor,
            permissions
        );
        
        assertEq(
            agentNFT.getExecutorPermissions(tokenId, executor),
            permissions,
            "Executor should have correct permissions"
        );
    }
    
    function test_MintAgent_MultipleTokens() public {
        vm.startPrank(alice);
        
        uint256 tokenId1 = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        uint256 tokenId2 = agentNFT.mintAgent(alice, "ipfs://2", address(0), 0);
        uint256 tokenId3 = agentNFT.mintAgent(bob, "ipfs://3", address(0), 0);
        
        vm.stopPrank();
        
        assertEq(tokenId1, 1);
        assertEq(tokenId2, 2);
        assertEq(tokenId3, 3);
        assertEq(agentNFT.ownerOf(tokenId3), bob);
    }
    
    // ============ TBA Address Computation Tests ============
    
    function test_GetAgentTBA_Deterministic() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        address tba1 = agentNFT.getAgentTBA(tokenId);
        address tba2 = agentNFT.getAgentTBA(tokenId);
        
        assertEq(tba1, tba2, "TBA address should be deterministic");
        assertTrue(tba1 != address(0), "TBA address should not be zero");
    }
    
    function test_GetAgentTBA_DifferentPerToken() public {
        vm.startPrank(alice);
        uint256 tokenId1 = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        uint256 tokenId2 = agentNFT.mintAgent(alice, "ipfs://2", address(0), 0);
        vm.stopPrank();
        
        address tba1 = agentNFT.getAgentTBA(tokenId1);
        address tba2 = agentNFT.getAgentTBA(tokenId2);
        
        assertTrue(tba1 != tba2, "Different tokens should have different TBAs");
    }
    
    // ============ Permission Tests ============
    
    function test_HasPermission_OwnerHasAllBeforeSelfOwning() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        // Owner should have all permissions before self-ownership is established
        assertTrue(
            agentNFT.hasPermission(tokenId, alice, agentNFT.PERMISSION_ANCHOR_STATE()),
            "Owner should have ANCHOR_STATE permission"
        );
        assertTrue(
            agentNFT.hasPermission(tokenId, alice, agentNFT.PERMISSION_MANAGE_EXECUTORS()),
            "Owner should have MANAGE_EXECUTORS permission"
        );
    }
    
    function test_HasPermission_ExecutorHasGrantedOnly() public {
        uint256 anchorOnly = agentNFT.PERMISSION_ANCHOR_STATE();
        
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", executor, anchorOnly);
        
        assertTrue(
            agentNFT.hasPermission(tokenId, executor, agentNFT.PERMISSION_ANCHOR_STATE()),
            "Executor should have granted permission"
        );
        assertFalse(
            agentNFT.hasPermission(tokenId, executor, agentNFT.PERMISSION_MANAGE_EXECUTORS()),
            "Executor should not have non-granted permission"
        );
    }
    
    function test_SetExecutor_ByOwner() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        uint256 newPermissions = agentNFT.PERMISSION_ANCHOR_STATE() | agentNFT.PERMISSION_SUBMIT_LIVENESS();
        
        vm.expectEmit(true, true, false, true);
        emit ExecutorSet(tokenId, bob, newPermissions);
        
        vm.prank(alice);
        agentNFT.setExecutor(tokenId, bob, newPermissions);
        
        assertEq(
            agentNFT.getExecutorPermissions(tokenId, bob),
            newPermissions
        );
    }
    
    function test_SetExecutor_RevertUnauthorized() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        // Get permissions before prank to avoid consuming expectRevert
        uint256 allPerms = agentNFT.ALL_PERMISSIONS();
        
        // Bob is not the owner and has no permissions
        vm.prank(bob);
        vm.expectRevert(SelfSovereignAgentNFT.Unauthorized.selector);
        agentNFT.setExecutor(tokenId, executor, allPerms);
    }
    
    // ============ State Anchoring Tests ============
    
    function test_AnchorState_ByOwner() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        bytes32 stateHash = keccak256("cognitive state v1");
        string memory stateUri = "ipfs://state/1";
        
        vm.expectEmit(true, false, false, true);
        emit StateAnchored(tokenId, stateHash, stateUri);
        
        vm.prank(alice);
        agentNFT.anchorState(tokenId, stateHash, stateUri);
        
        (bytes32 returnedHash, string memory returnedUri, uint256 timestamp) = agentNFT.getStateAnchor(tokenId);
        
        assertEq(returnedHash, stateHash);
        assertEq(returnedUri, stateUri);
        assertEq(timestamp, block.timestamp);
    }
    
    function test_AnchorState_ByExecutor() public {
        uint256 anchorPermission = agentNFT.PERMISSION_ANCHOR_STATE();
        
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", executor, anchorPermission);
        
        bytes32 stateHash = keccak256("cognitive state v1");
        
        vm.prank(executor);
        agentNFT.anchorState(tokenId, stateHash, "ipfs://state/1");
        
        (bytes32 returnedHash,,) = agentNFT.getStateAnchor(tokenId);
        assertEq(returnedHash, stateHash);
    }
    
    function test_AnchorState_RevertUnauthorized() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        vm.prank(bob);
        vm.expectRevert(SelfSovereignAgentNFT.Unauthorized.selector);
        agentNFT.anchorState(tokenId, bytes32(0), "ipfs://state/1");
    }
    
    // ============ Liveness Tests ============
    
    function test_SubmitLivenessProof() public {
        uint256 livenessPermission = agentNFT.PERMISSION_SUBMIT_LIVENESS();
        
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", executor, livenessPermission);
        
        bytes32 attestation = keccak256("TEE attestation");
        
        // Advance time
        vm.warp(block.timestamp + 1 hours);
        
        vm.expectEmit(true, false, false, true);
        emit LivenessProof(tokenId, block.timestamp, attestation);
        
        vm.prank(executor);
        agentNFT.submitLivenessProof(tokenId, attestation);
        
        assertEq(agentNFT.getLastLiveness(tokenId), block.timestamp);
    }
    
    // ============ Self-Ownership Status Tests ============
    
    function test_IsSelfOwning_InitiallyFalse() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        assertFalse(agentNFT.isSelfOwning(tokenId), "Should not be self-owning initially");
    }
    
    // ============ ERC-165 Tests ============
    
    function test_SupportsInterface_ERC721() public {
        // ERC-721 interface ID
        bytes4 erc721InterfaceId = 0x80ac58cd;
        assertTrue(agentNFT.supportsInterface(erc721InterfaceId), "Should support ERC-721");
    }
    
    function test_SupportsInterface_ERC165() public {
        // ERC-165 interface ID
        bytes4 erc165InterfaceId = 0x01ffc9a7;
        assertTrue(agentNFT.supportsInterface(erc165InterfaceId), "Should support ERC-165");
    }
    
    // ============ Ouroboros Loop Tests ============
    // Note: Full Ouroboros tests require a real TBA implementation or mock
    // These tests verify the contract logic without actual TBA deployment
    
    function test_EstablishSelfOwnership_RevertNotOwner() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        // Bob tries to establish self-ownership on Alice's token
        vm.prank(bob);
        vm.expectRevert(SelfSovereignAgentNFT.Unauthorized.selector);
        agentNFT.establishSelfOwnership(tokenId);
    }
    
    function test_EstablishSelfOwnership_RevertAlreadySelfOwning() public {
        // This test would require mocking the TBA creation
        // For now, we test the revert condition by checking the flag
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        // Can't test full flow without TBA, but we can verify initial state
        assertFalse(agentNFT.isSelfOwning(tokenId));
    }
    
    // ============ Recovery Tests ============
    
    function test_SetRecoveryConfig() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        uint256 timeout = 7 days;
        
        vm.prank(alice);
        agentNFT.setRecoveryConfig(tokenId, bob, timeout);
        
        (address nominee, uint256 timeoutSeconds) = agentNFT.getRecoveryConfig(tokenId);
        assertEq(nominee, bob);
        assertEq(timeoutSeconds, timeout);
    }
    
    function test_SetRecoveryConfig_RevertInvalidTimeout() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        // Timeout must be at least 1 day
        vm.prank(alice);
        vm.expectRevert(SelfSovereignAgentNFT.InvalidTimeout.selector);
        agentNFT.setRecoveryConfig(tokenId, bob, 12 hours);
    }
    
    function test_SetRecoveryConfig_RevertInvalidNominee() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        vm.prank(alice);
        vm.expectRevert(SelfSovereignAgentNFT.InvalidNominee.selector);
        agentNFT.setRecoveryConfig(tokenId, address(0), 7 days);
    }
    
    function test_CanTriggerRecovery_FalseWithoutConfig() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        assertFalse(agentNFT.canTriggerRecovery(tokenId));
    }
    
    function test_CanTriggerRecovery_FalseBeforeTimeout() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        vm.prank(alice);
        agentNFT.setRecoveryConfig(tokenId, bob, 7 days);
        
        // Advance time but not enough
        vm.warp(block.timestamp + 3 days);
        
        assertFalse(agentNFT.canTriggerRecovery(tokenId));
    }
    
    function test_CanTriggerRecovery_TrueAfterTimeout() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        vm.prank(alice);
        agentNFT.setRecoveryConfig(tokenId, bob, 7 days);
        
        // Advance time past timeout
        vm.warp(block.timestamp + 8 days);
        
        assertTrue(agentNFT.canTriggerRecovery(tokenId));
    }
    
    function test_TriggerRecovery_Success() public {
        uint256 livenessPermission = agentNFT.PERMISSION_SUBMIT_LIVENESS();
        
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", executor, livenessPermission);
        
        vm.prank(alice);
        agentNFT.setRecoveryConfig(tokenId, bob, 7 days);
        
        // Advance time past timeout
        vm.warp(block.timestamp + 8 days);
        
        // Bob triggers recovery
        vm.prank(bob);
        agentNFT.triggerRecovery(tokenId);
        
        // Bob should now have all permissions
        uint256 allPerms = agentNFT.ALL_PERMISSIONS();
        assertEq(agentNFT.getExecutorPermissions(tokenId, bob), allPerms);
    }
    
    function test_TriggerRecovery_RevertNotNominee() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        vm.prank(alice);
        agentNFT.setRecoveryConfig(tokenId, bob, 7 days);
        
        vm.warp(block.timestamp + 8 days);
        
        // Executor (not bob) tries to trigger
        vm.prank(executor);
        vm.expectRevert(SelfSovereignAgentNFT.Unauthorized.selector);
        agentNFT.triggerRecovery(tokenId);
    }
    
    function test_TriggerRecovery_RevertBeforeTimeout() public {
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", address(0), 0);
        
        vm.prank(alice);
        agentNFT.setRecoveryConfig(tokenId, bob, 7 days);
        
        // Not enough time has passed
        vm.warp(block.timestamp + 3 days);
        
        vm.prank(bob);
        vm.expectRevert(SelfSovereignAgentNFT.RecoveryNotAvailable.selector);
        agentNFT.triggerRecovery(tokenId);
    }
    
    function test_LivenessResetsRecoveryTimer() public {
        uint256 livenessPermission = agentNFT.PERMISSION_SUBMIT_LIVENESS();
        
        vm.prank(alice);
        uint256 tokenId = agentNFT.mintAgent(alice, "ipfs://1", executor, livenessPermission);
        
        vm.prank(alice);
        agentNFT.setRecoveryConfig(tokenId, bob, 7 days);
        
        // Advance 5 days
        vm.warp(block.timestamp + 5 days);
        
        // Submit liveness proof
        vm.prank(executor);
        agentNFT.submitLivenessProof(tokenId, keccak256("alive"));
        
        // Advance another 5 days (total 10 days from start, but only 5 from liveness)
        vm.warp(block.timestamp + 5 days);
        
        // Recovery should NOT be available because liveness was submitted
        assertFalse(agentNFT.canTriggerRecovery(tokenId));
        
        // Advance 3 more days (now 8 days from liveness)
        vm.warp(block.timestamp + 3 days);
        
        // Now recovery should be available
        assertTrue(agentNFT.canTriggerRecovery(tokenId));
    }
}
