/**
 * Lit Action: Kieran's Transaction Signing Policy
 * 
 * This JavaScript code runs inside Lit Protocol's TEE (Trusted Execution Environment).
 * It defines the policy for WHEN the PKP is allowed to sign transactions.
 * 
 * Version: 1.0.0 (Simple)
 * - Trusts any authorized session sig holder
 * - Signs any transaction hash provided
 * 
 * Future versions can add constraints like:
 * - Only sign TBA execute() calls
 * - Rate limiting
 * - Destination address whitelisting
 * - Value limits
 * 
 * Parameters (passed via jsParams from Python):
 * - toSign: The message/transaction hash to sign (as byte array)
 * - publicKey: The PKP's public key
 * - sigName: Name for the signature in the response
 * 
 * Security Note:
 * For production, upload this to IPFS and reference by CID for immutability.
 * This ensures the signing policy cannot be modified without changing the CID.
 */

const litActionCode = `
(async () => {
  try {
    // Log for debugging (visible in Lit Explorer)
    console.log("Kieran's Lit Action executing...");
    console.log("Public Key:", publicKey);
    console.log("Message to sign length:", toSign.length);
    
    // ============================================================
    // POLICY CHECK (Simple Version)
    // ============================================================
    // In this simple version, we trust that if the caller has valid
    // session sigs, they are authorized to request signatures.
    // 
    // Future enhancements could add:
    // - Check Lit.Auth for specific auth method requirements
    // - Verify transaction data matches expected patterns
    // - Rate limiting via external API calls
    // - Time-based restrictions
    
    const isAuthorized = true;  // Simple: trust session sig holder
    
    if (!isAuthorized) {
      Lit.Actions.setResponse({ 
        response: JSON.stringify({
          success: false,
          error: "Unauthorized: Policy check failed"
        })
      });
      return;
    }
    
    // ============================================================
    // SIGN THE MESSAGE
    // ============================================================
    // signAndCombineEcdsa collects partial signatures from threshold
    // nodes and combines them into a valid ECDSA signature.
    
    console.log("Policy check passed, signing...");
    
    const sigShare = await Lit.Actions.signAndCombineEcdsa({
      toSign: toSign,
      publicKey: publicKey,
      sigName: sigName || "kieran_sig"
    });
    
    // ============================================================
    // RETURN THE SIGNATURE
    // ============================================================
    // The signature is returned as a JSON string containing r, s, v
    
    console.log("Signature generated successfully");
    
    Lit.Actions.setResponse({ 
      response: JSON.stringify({
        success: true,
        signature: sigShare,
        timestamp: Date.now()
      })
    });
    
  } catch (error) {
    console.error("Lit Action error:", error.message);
    Lit.Actions.setResponse({ 
      response: JSON.stringify({
        success: false,
        error: error.message
      })
    });
  }
})();
`;

// Export for use in Python scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { litActionCode };
}

// Also make available as a string for direct use
const LIT_ACTION_CODE = litActionCode;
