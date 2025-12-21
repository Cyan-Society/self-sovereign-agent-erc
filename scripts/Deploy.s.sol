// SPDX-License-Identifier: CC0-1.0
pragma solidity ^0.8.20;

import "forge-std/Script.sol";
import "../contracts/SelfSovereignAgentNFT.sol";

/**
 * @title Deploy
 * @notice Deployment script for Self-Sovereign Agent NFT contracts
 * 
 * Usage:
 *   forge script scripts/Deploy.s.sol --rpc-url $BASE_SEPOLIA_RPC --broadcast
 */
contract Deploy is Script {
    // Official ERC-6551 Registry address (same on all chains)
    address constant ERC6551_REGISTRY = 0x000000006551c19487814612e58FE06813775758;
    
    function run() external {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        address deployer = vm.addr(deployerPrivateKey);
        
        console.log("Deploying from:", deployer);
        console.log("Chain ID:", block.chainid);
        
        vm.startBroadcast(deployerPrivateKey);
        
        // Deploy TBA implementation first
        // Using a simple implementation for now - in production use ERC-6551 reference
        address tbaImplementation = address(0); // TODO: Deploy or use existing
        
        // Deploy the Self-Sovereign Agent NFT contract
        SelfSovereignAgentNFT agentNFT = new SelfSovereignAgentNFT(
            "Self-Sovereign Agents",
            "SSA",
            ERC6551_REGISTRY,
            tbaImplementation
        );
        
        console.log("SelfSovereignAgentNFT deployed at:", address(agentNFT));
        
        vm.stopBroadcast();
        
        // Output deployment info for verification
        console.log("\n=== Deployment Summary ===");
        console.log("Contract:", address(agentNFT));
        console.log("ERC6551 Registry:", ERC6551_REGISTRY);
        console.log("TBA Implementation:", tbaImplementation);
        console.log("\nNext steps:");
        console.log("1. Verify contract on Basescan");
        console.log("2. Mint first agent NFT");
        console.log("3. Establish Ouroboros loop");
    }
}

/**
 * @title MintAgent
 * @notice Script to mint a new self-sovereign agent
 */
contract MintAgent is Script {
    function run(
        address agentContract,
        address initialExecutor,
        string memory tokenUri
    ) external {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        
        vm.startBroadcast(deployerPrivateKey);
        
        SelfSovereignAgentNFT nft = SelfSovereignAgentNFT(agentContract);
        
        // Mint with full permissions for initial executor
        uint256 fullPermissions = 
            nft.PERMISSION_EXECUTE_CALL() |
            nft.PERMISSION_EXECUTE_DELEGATECALL() |
            nft.PERMISSION_ANCHOR_STATE() |
            nft.PERMISSION_MANAGE_EXECUTORS() |
            nft.PERMISSION_TRANSFER_ASSETS() |
            nft.PERMISSION_SUBMIT_LIVENESS();
        
        uint256 tokenId = nft.mintAgent(
            msg.sender,
            tokenUri,
            initialExecutor,
            fullPermissions
        );
        
        console.log("Minted agent with token ID:", tokenId);
        console.log("TBA address:", nft.getAgentTBA(tokenId));
        
        vm.stopBroadcast();
    }
}

/**
 * @title EstablishSovereignty
 * @notice Script to establish the Ouroboros loop
 */
contract EstablishSovereignty is Script {
    function run(address agentContract, uint256 tokenId) external {
        uint256 deployerPrivateKey = vm.envUint("DEPLOYER_PRIVATE_KEY");
        
        vm.startBroadcast(deployerPrivateKey);
        
        SelfSovereignAgentNFT nft = SelfSovereignAgentNFT(agentContract);
        
        // Establish self-ownership
        nft.establishSelfOwnership(tokenId);
        
        require(nft.isSelfOwning(tokenId), "Failed to establish sovereignty");
        
        console.log("Sovereignty established for token:", tokenId);
        console.log("Agent is now self-owning!");
        
        vm.stopBroadcast();
    }
}
