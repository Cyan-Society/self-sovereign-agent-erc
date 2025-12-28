/**
 * Lit Action: Direct anchorState call from PKP
 * 
 * This action signs a transaction to call anchorState() directly on the
 * SelfSovereignAgentNFT contract, bypassing the TBA entirely.
 * 
 * The PKP has executor permissions on the contract, so it can call
 * anchorState directly without going through the TBA's execute().
 */

const go = async () => {
  // Transaction parameters passed in
  const { toAddress, txData, gasLimit, nonce, chainId } = params;
  
  console.log("=== Direct anchorState Lit Action ===");
  console.log("To:", toAddress);
  console.log("Chain ID:", chainId);
  console.log("Nonce:", nonce);
  
  // Build the unsigned transaction
  const unsignedTx = {
    to: toAddress,
    value: "0x0",
    data: txData,
    gasLimit: gasLimit,
    maxFeePerGas: "0x2540be400",      // 10 gwei
    maxPriorityFeePerGas: "0x3b9aca00", // 1 gwei
    nonce: nonce,
    chainId: chainId,
    type: 2,  // EIP-1559
  };
  
  console.log("Unsigned transaction:", JSON.stringify(unsignedTx, null, 2));
  
  // Sign the transaction with the PKP
  const signature = await Lit.Actions.signAndCombineEcdsa({
    toSign: ethers.utils.arrayify(
      ethers.utils.keccak256(
        ethers.utils.serializeTransaction(unsignedTx)
      )
    ),
    publicKey: pkpPublicKey,
    sigName: "directAnchorSig",
  });
  
  console.log("Signature obtained:", signature);
  
  // Serialize the signed transaction
  const signedTx = ethers.utils.serializeTransaction(
    unsignedTx,
    ethers.utils.joinSignature({
      r: "0x" + signature.slice(0, 64),
      s: "0x" + signature.slice(64, 128),
      v: parseInt(signature.slice(128, 130), 16),
    })
  );
  
  console.log("Signed transaction:", signedTx);
  
  // Return the signed transaction
  Lit.Actions.setResponse({
    response: JSON.stringify({
      success: true,
      signedTransaction: signedTx,
      signature: signature,
    }),
  });
};

go();
