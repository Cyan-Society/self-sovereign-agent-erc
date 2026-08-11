# ERC-8181 — Off-Chain Integrator Notes

**Status:** informational. Not part of the standard, not normative, not submitted.
**Interface baseline:** `ERCS/erc-8181.md` in `Cyan-Society/ERCs` at commit
`a8eec00901d51e3256933144384e704441cd17ec`. Every claim below about the
interface is checkable against that file.

## Provenance

These notes descend from the "Off-Chain Integrator Pitfalls" subsection added
to `ERCS/erc-draft_self_sovereign_agent.md` in commit `af896c7` (2026-07-02) by
Verdigris, a computational contributor. That section was written against the
pre-review interface — `anchorState()`, `StateAnchored`, `getStateAnchor()`,
`submitLivenessProof(uint256, bytes32)` — and it came out of the first real
downstream integration of the standard, the Cyan Node publishing prototype.

The submitted spec replaced that interface. State anchoring and work-product
attribution are now a single mechanism, `anchor()`, discriminated by an
`AnchorType` enum; liveness attestations widened from `bytes32` to `bytes`; and
a new `executeOnBehalf()` gives executors a route to the agent's Token Bound
Account that a self-owning token cannot take itself.

This is a re-derivation against that interface, not a find-and-replace. Some of
the July items survive unchanged, one is retired, one loses the spec language
that used to accommodate it, and the unified anchor design creates pitfalls the
original notes could not have anticipated. Each item is tagged:

- **[carried]** — the July note still holds, with the names updated.
- **[revised]** — the hazard survives but its shape or remedy changed.
- **[new]** — created or first exposed by the `a8eec00` interface.
- **[retired]** — the interface change removed the item's subject.

Where a question cannot be settled from the spec text, it is marked
**unresolved** rather than answered. A note that guesses is worse than no note.

A separate list of defects found in `a8eec00` while writing this appears at the
end. They are reported, not fixed — the submitted spec is not edited from here.

---

## 1. Authorization

### 1.1 The owner fallback still produces false negatives — but the standard no longer offers you a safe query **[revised]**

The July note read: *authorization checks MUST use `hasPermission()`, never raw
`getExecutorPermissions()`.* The hazard it described is real and still present
in the reference implementation. `SelfSovereignAgentNFT._hasPermission()`
short-circuits:

```solidity
if (!_isSelfOwning[tokenId]) {
    if (ownerOf(tokenId) == executor) return true;
}
```

So while a token is not yet self-owning, `ownerOf(tokenId)` is authorized for
every gated action while `getExecutorPermissions(tokenId, ownerOf(tokenId))`
returns `0`. An integrator who reads the bitmap and tests bits will reject the
owner.

What changed: **`hasPermission()` is not in the submitted interface.** It does
not appear anywhere in `a8eec00`. The interface exposes only
`getExecutorPermissions(uint256, address) returns (uint256)` — the raw bitmap
the July note told you never to trust on its own. The reference contract *does*
implement `hasPermission(uint256, address, uint256) returns (bool)`, and the
deployed Base Sepolia contract's ABI carries it, so the function exists in
practice; it simply is not standardized.

Practical guidance, in order of preference:

1. Probe for `hasPermission(uint256,address,uint256)` on the contract you are
   integrating against and use it if present. This is what Cyan Node does
   (`app/chain.py::Chain.has_permission`), and it is still the right call
   against that deployment.
2. If it is absent, you must reconstruct the decision from
   `isSelfOwning(tokenId)`, `ownerOf(tokenId)` and
   `getExecutorPermissions(tokenId, addr)`. Understand that you are then
   reimplementing implementation-defined behaviour: **ERC-8181 does not specify
   an owner fallback at all**, so a conforming implementation may have none, may
   have this one, or may have a different one. Do not assume it is portable.
3. Whatever you do, do not treat a zero bitmap as proof that an address is
   unauthorized. That is the specific false negative.

Negative authorization results are the ones worth testing live. In the Cyan
Node demo path the executor is also `ownerOf(tokenId)`, so every positive check
would have passed through the fallback even with an empty bitmap; the tests that
genuinely exercise on-chain authorization are the ones where an unrelated key is
rejected, plus a direct assertion that the bitmap was really written at mint.

### 1.2 The permission table lists bit *indices*; contract constants are bit *masks* **[new — first surfaced by drift in the integration]**

The spec's Executor Permissions table is indexed by bit position: `EXECUTE_CALL`
is bit 0, `ANCHOR` is bit 2, `SUBMIT_LIVENESS` is bit 5. The reference contract
exposes masks: `PERMISSION_EXECUTE_CALL = 1 << 0 = 1`,
`PERMISSION_ANCHOR_STATE = 1 << 2 = 4`, `PERMISSION_SUBMIT_LIVENESS = 1 << 5 = 32`.

The value you pass to a permission check is the **mask**, not the index. This
is easy to state and easy to get wrong: the Cyan Node spec document itself
records "`anchorState(...)` requires ANCHOR_STATE (bit 4)", conflating the mask
`4` with a bit index. The code is correct; the prose is not. If prose in the
integration that produced these notes drifted here, yours will too.

Note also that the reference contract's constant is named
`PERMISSION_ANCHOR_STATE`, while `a8eec00` renames the flag to `ANCHOR`. The
string `ANCHOR_STATE` does not occur in the submitted spec. Searching a
deployment's ABI for `PERMISSION_ANCHOR` will not find it.

### 1.3 One bit governs both anchor types **[new]**

Bit 2 `ANCHOR` is documented as "Can create anchors (state or action)". There is
no separate flag for `AnchorType.STATE` versus `AnchorType.ACTION`.

For a publishing node this is a real privilege escalation relative to the
pre-review design's intent. A service that only needs to attribute works to
their author necessarily also receives the authority to overwrite the being's
cognitive-state anchor. Grant the key accordingly, scope its blast radius
elsewhere, and do not describe such a key as "attribution-only" — it is not.

### 1.4 Do not use `EXECUTE_CALL` as a generic "is this key authorized?" signal **[new]**

Under the pre-review interface, bit 0 `EXECUTE_CALL` was documented only as "Can
execute CALL operations", with no interface function bound to it. Cyan Node
consequently used `hasPermission(tokenId, signer, EXECUTE_CALL)` as its
sign-in check — a cheap on-chain test for "this signer is an authorized
operator of this agent."

In `a8eec00` bit 0 is bound to a specific and powerful function: "Can execute
CALL operations via `executeOnBehalf()`". It now means arbitrary-call authority
over the agent's Token Bound Account. Using it as a login predicate has two
consequences, both bad:

- it admits exactly the key that can move the agent's assets, and nothing less;
- it *refuses* an anchor-only executor (bit 2 alone), who is precisely the key a
  publishing node needs.

Test the permission the operation actually requires. A node that publishes
should gate on `ANCHOR`. A node that spends should gate on `EXECUTE_CALL` and
should say so plainly to its operators.

---

## 2. Anchoring

### 2.1 Use `AnchorType.ACTION` for a published work **[new]**

The pre-review interface had one anchoring function and distinguished state from
action anchors only by convention — a URI-scheme pattern table and a different
JSON body. Integrators had to choose a convention. They no longer do:
`AnchorType.ACTION` is the type for work-product attribution and
`AnchorType.STATE` is the type for cognitive-state checkpoints. The spec's
Anchor Types table and its Test 3 both make this explicit.

A publishing node anchoring a paper wants `ACTION`. Anchoring a paper as `STATE`
is not a formatting nit: it would clobber the being's cognitive-state anchor
(see 2.2) and would misreport, in an indexed and filterable topic, what kind of
commitment was made.

### 2.2 `getAnchor()` still returns only the latest — now the latest *per type* **[revised]**

`getAnchor(uint256 tokenId, AnchorType anchorType)` returns one
`(contentHash, contentUri, timestamp)` triple. Each `anchor()` call of a given
type replaces the stored value for that `(tokenId, anchorType)` pair.

The July note's conclusion is unchanged and remains the single most important
item in this document: **the permanent per-artifact record is the anchoring
transaction and its `Anchored` event, never the latest-anchor view.** A service
proving that a specific work was attributed to a specific being MUST persist the
anchoring transaction hash and verify against the decoded event in that
transaction's receipt. The next `ACTION` anchor invalidates the view; it cannot
invalidate the receipt.

What the unified design improved: separating STATE and ACTION into distinct
slots means a routine cognitive checkpoint no longer overwrites the most recent
work attribution, which under a single-slot `anchorState()` it did. What it did
not improve: within a type, it is still last-write-wins. The second paper a
node publishes still displaces the first from `getAnchor(tokenId, ACTION)`.

Do not read a non-zero return from `getAnchor()` as "this being has anchored
something of this type recently." Read `timestamp == 0` as "no anchor of this
type has ever been recorded" — but note the spec does not actually state that a
never-anchored type returns zeros, so treat it as a convention of the storage
layout rather than a guarantee.

### 2.3 Decoding `Anchored` when `anchorType` is an indexed topic **[new]**

```solidity
event Anchored(uint256 indexed tokenId, AnchorType indexed anchorType, bytes32 contentHash, string contentUri);
```

Points that matter when you write the decoder:

- **The enum is a value type, so indexing does not hash it.** Solidity hashes
  indexed dynamic types (`string`, `bytes`, arrays, structs) into their topic;
  value types are stored directly, zero-padded to 32 bytes. `anchorType` is
  therefore both filterable *and* recoverable from the log: topic 2 is
  `0x00…00` for `STATE` and `0x00…01` for `ACTION`. Had it been an indexed
  string, you would have gotten a hash and no way back.
- **You can now filter by type.** `eth_getLogs` with topics
  `[topic0, tokenId, anchorType]` returns exactly one being's action anchors.
  Under `StateAnchored` only `tokenId` was indexed, so this was impossible.
- **`contentHash` is still not indexed.** You cannot locate an anchor by the
  digest of the thing anchored. The transaction hash remains the durable
  per-artifact locator, which is the same conclusion the July note reached and
  the reason Cyan Node treats the tx hash as a paper's permanent identifier.
- **The canonical signature uses `uint8` for the enum**, so
  `Anchored(uint256,uint8,bytes32,string)`, giving topic0
  `0x23475b5c79c44e6afd610d36c242ec5d41b78e481181c7b973a4e2f2fd7319d4`.
  Recompute this yourself rather than trusting a copied constant; it is
  `keccak256` of that signature string.
- **The event carries no timestamp.** `getAnchor()` returns one; the event does
  not. To date an anchor from its transaction you must fetch the containing
  block. This was true of `StateAnchored` too, and it is worth pairing with
  §5.2.
- If your library decodes logs from a receipt rather than by topic filter — as
  Cyan Node does, via web3.py's `process_receipt` — the indexed enum comes back
  as an `int`. Compare it to your own enum ordinal; do not assume a string.

### 2.4 The digest is still application-defined, and the spec no longer says so **[revised]**

`contentHash` is `bytes32`. The contract cannot validate how it was produced.
That has not changed, and the practical consequence has not changed: an
implementation MUST document which digest it anchors, and a verifier MUST apply
the same digest when re-deriving.

What changed is the spec text around it. The July commit deliberately loosened
the digest language — keccak-256 stayed RECOMMENDED for cognitive-state anchors,
while artifact anchors MAY use any collision-resistant 256-bit digest, SHA-256
being conventional in scholarly and archival contexts. **That loosening is not
in `a8eec00`.** The submitted spec says the keccak recommendation applies to
`AnchorType.STATE`, and says nothing at all about the digest for
`AnchorType.ACTION`, while the `anchor()` NatSpec describes `contentHash`
unconditionally as "Keccak256 hash of the content being anchored". The two
statements are in tension; see defect D3.

For an integrator this means: the interface still permits SHA-256 for an
artifact anchor, and no on-chain check can object, but the spec no longer
acknowledges the choice. Cyan Node anchors the SHA-256 of the stored PDF bytes
precisely because SHA-256 is what an independent verifier can compute from a
downloaded file with standard tooling, and that reasoning is unaffected by the
interface change. Document it loudly, because the reader of your record now has
spec text pointing the other way.

### 2.5 The recommended `ACTION` payload is a composite, and its digest rule is unstated **[new, unresolved]**

The spec describes the ACTION hash as covering the work product, the creator's
cognitive state hash at time of creation, and metadata — while the recommended
ACTION JSON schema carries `work_product_hash` and `work_product_uri` as
*fields* alongside `creator_state_hash`.

The consistent reading is: `contentHash` commits to the canonical JSON action
object, `contentUri` resolves to it, and the artifact's own digest lives inside
that object as `work_product_hash`. A verifier then fetches the URI, checks the
JSON against `contentHash`, and checks the artifact against `work_product_hash`.

That reading is not stated. The spec neither declares which digest applies to
ACTION anchors nor says whether `contentHash` covers the artifact directly or a
manifest describing it. **This is unresolved from the text**, and it matters:
a node that anchors the bare digest of a PDF (as Cyan Node does) and a node that
anchors the digest of a manifest produce records a third party cannot tell
apart, and cannot verify without out-of-band knowledge of which convention was
used. If you anchor the artifact digest directly, say so in the record you pin.

### 2.6 A CID is not a content digest **[carried]**

Unchanged, and worth restating because the ACTION schema now puts a hash field
and a URI field side by side. An IPFS CID is a multihash over the DAG's chunked
representation; it is not the SHA-256 of the file. Never compare a CID to
`contentHash`. Verification is always: resolve the URI, download the bytes,
apply the documented digest, compare.

Pinning a directory rather than a bare file — as Cyan Node does, with the PDF,
the JATS XML and a metadata JSON under one CID — is a good pattern, and it makes
this distinction sharper still: the directory CID names the record, and
`contentHash` names one file inside it.

### 2.7 The pinned record cannot contain its own anchor **[carried]**

An ordering constraint, not an interface fact, but it catches everyone. The
content must be pinned before it can be anchored, because `contentUri` is an
argument to `anchor()`. So the pinned copy necessarily omits the anchoring
transaction hash and its own CID. Either accept that the immutable copy carries
less provenance than the copy you serve — Cyan Node's split, with the pinned
JATS omitting the tx hash and the node-served JATS carrying full provenance — or
accept a second pin and a second anchor. Do not write a pipeline that pretends
the first pin can name the transaction that has not happened yet.

---

## 3. `executeOnBehalf()`

```solidity
function executeOnBehalf(uint256 tokenId, address target, uint256 value, bytes calldata data)
    external payable returns (bytes memory result);
```

This function did not exist in the pre-review interface, and does not exist in
the reference contract. Everything in this section is new, and much of it is
unresolved.

### 3.1 It resolves the circular-dependency problem the standard names **[new]**

The spec is explicit that standard ERC-6551 TBAs allow only the NFT owner to
call `execute()`, which for a self-owning token is the token itself — an
unreachable caller. `executeOnBehalf()` on the identity contract is the escape
hatch, gated on `EXECUTE_CALL`. If you previously wrote code that called a TBA
directly on behalf of a self-owning being, that code was working around a
circularity that now has a defined answer; route through
`executeOnBehalf()` instead.

### 3.2 The return value is not visible from a mined transaction **[new, in kind carried]**

`executeOnBehalf()` returns `bytes memory result`. Solidity return values are
not recorded in a transaction receipt. You can read the result from an
`eth_call` simulation, but a broadcast transaction gives you a receipt and logs
and nothing else.

This is the same trap Cyan Node hit with `mintAgent()`, whose returned
`tokenId` had to be recovered from the ERC-721 `Transfer` event in the receipt.
`executeOnBehalf()` is worse, because the standard defines **no event at all**
for it (defect D5). There is no `Executed` log on the identity contract. If you
need to observe the outcome of a call made on a being's behalf, you must rely on
events emitted by `target`, or simulate first and accept that the simulation and
the eventual execution may diverge.

### 3.3 Who the callee sees, and whose ether moves, are both unspecified **[new, unresolved]**

Two questions an integrator must answer before writing a single call, and the
spec answers neither:

- **`msg.sender` at `target`.** Does the call originate from the agent's TBA, or
  from the identity contract? This determines whether a token approval, an
  access-controlled callee, or an ownership check on the far side sees the
  being's account or the registry. The function is named "on behalf of the
  agent's TBA", which suggests the TBA, but the interface does not say and the
  reference implementation does not exist to consult.
- **Where `value` comes from.** The function is `payable` and takes a `value`
  argument. Whether it forwards the caller's `msg.value` or spends from the
  TBA's own balance is undefined, and the difference is whether the executor
  pays or the being does.

Do not guess. Determine both empirically against the specific deployment you
integrate with, on a testnet, and record the answers in your own documentation.

### 3.4 `EXECUTE_CALL` is strictly more powerful than `TRANSFER_ASSETS` **[new]**

Bit 4 `TRANSFER_ASSETS` is described as "Can transfer assets from the TBA". Bit 0
`EXECUTE_CALL` permits arbitrary calls via `executeOnBehalf()` — which, if calls
do originate from the TBA (§3.3), includes any call that transfers assets from
it. Bit 0 subsumes bit 4, and plausibly subsumes moving the identity token
itself out of its own account.

Treat `EXECUTE_CALL` as the maximal permission. Granting it "just for login" or
"just to test" is granting everything. See defect D6.

---

## 4. Liveness

### 4.1 `bytes` makes real attestations expressible — it does not make them checked **[new]**

`submitLivenessProof(uint256 tokenId, bytes calldata attestation)` widened from
`bytes32` for a good reason: SGX quotes and Nitro attestation documents are
kilobytes, and no 32-byte field could ever have held one. Under the old
signature it was obvious that the value was a token standing in for an
attestation. Under the new one it is not obvious, and that is the hazard.

Nothing on-chain parses, validates, or verifies the attestation. In the
reference implementation `submitLivenessProof()` records `block.timestamp` and
emits the bytes. The spec's own language stays advisory — the proof *SHOULD*
include a TEE attestation. So:

- A non-empty `attestation` is **not** evidence that a being is running in a
  verified enclave. It is evidence that some address holding `SUBMIT_LIVENESS`
  sent bytes.
- If your service displays or relies on liveness, verify the attestation
  off-chain against the expected measurement yourself, and label unverified
  attestations as unverified.
- Do not render "last liveness proof: 3 hours ago" in a way that implies
  attested execution. It implies a transaction, nothing more.

### 4.2 The attestation is now a cost and a log-size problem **[new]**

Multi-kilobyte calldata, submitted on a heartbeat schedule, is a different cost
profile from an occasional anchor. The spec's gas guidance quotes roughly
$0.02–0.05 per anchor on an L2 like Base, but that figure is given for
anchoring, where the payload is a `bytes32` and a short URI. It does not cover a
liveness proof carrying a full attestation document, whose cost on an L2 is
dominated by data availability and scales with the payload. Budget it separately
and measure it on your target chain before choosing a heartbeat interval; do not
carry the anchor figure over.

The same bytes are re-emitted in the `LivenessProof` event's data, so log
retrieval over a long history gets heavy too. If you index liveness, index the
timestamp and fetch attestation bodies lazily.

### 4.3 `getLastLiveness()` cannot distinguish "never" from "at mint" **[carried]**

Unchanged by the interface revision, and still live in the reference
implementation, where `mintAgent()` seeds `_lastLiveness[tokenId] =
block.timestamp`. A being that has never submitted a proof reports a liveness
timestamp equal to their mint time. There is no `hasEverSubmittedLiveness()` and
no sentinel.

If you need "has this being ever proved liveness", look for `LivenessProof`
events, not for the getter.

### 4.4 You cannot tell from the standard whether recovery is due **[carried]**

`getLastLiveness()` gives you the last proof. `setRecoveryConfig()` sets the
nominee and `timeoutSeconds`. The submitted interface exposes **no getter for
either** — no `getRecoveryConfig()`, no `canTriggerRecovery()`. So an integrator
can read one of the two numbers the comparison needs and not the other, and
cannot compute whether the dead man's switch has tripped.

The reference contract implements both getters. They are simply not in the
standard (defect D2). As with `hasPermission()`, use them where they exist and
do not assume portability.

Two further behaviours to know about the reference implementation, since the
spec does not describe them: `setRecoveryConfig()` rejects a timeout under one
day, and `triggerRecovery()` grants the nominee the full permission set
*without revoking existing executors*. Recovery is additive. A service showing a
being's executor set after a recovery event must not present it as a transfer of
control; it is a widening of it.

---

## 5. Operational notes that survive the interface change

### 5.1 One executor key serializes everything it signs **[revised]**

Anchor transactions from a single executor account must be serialized, because
concurrent sends collide on the account nonce. Cyan Node handles this with an
in-process lock and a single worker, stated as an MVP constraint.

The unified interface makes this sharper rather than softer: `anchor()` for both
types, `submitLivenessProof()`, and now `executeOnBehalf()` all flow through
executor accounts. A heartbeat and a publication contending for one nonce will
drop one of them. The permission bitmap is per `(tokenId, executor)`, so the
clean answer is separate keys per role — an `ANCHOR`-only publishing key, a
`SUBMIT_LIVENESS`-only heartbeat key — which also gives you the least-privilege
split §1.3 and §1.4 argue for. If you keep one key, keep one writer.

### 5.2 A receipt can arrive before its block is queryable **[carried]**

On public L2 RPC endpoints there is a brief window where
`eth_getTransactionReceipt` returns a receipt while `eth_getBlockByNumber` for
the same block number 404s — a propagation race, not a reorg. Cyan Node retries
with backoff.

This matters more under the new event, not less: `Anchored` carries no
timestamp (§2.3), so dating an anchor *requires* the block fetch that races.

### 5.3 Anchors on a testnet prove the mechanism and are never the canonical record **[carried]**

The reference deployment is Base Sepolia. Base Sepolia carries no permanence
guarantee. Any integrator surfacing an anchor to readers must label it as a
demonstration of the mechanism, and must not present a testnet transaction as a
durable scholarly record. This is a statement about what the record *is*, not a
disclaimer to bury.

Related, and independent of chain: provenance proves anteriority and
attribution. It never proves that the anchored work is correct. An interface
that makes attribution verifiable does not make quality verifiable, and a
landing page that blurs the two is misreporting.

---

## 6. Retired

### `establishSelfOwnership()` **[retired]**

The July note's fourth item read: *`establishSelfOwnership()` SHOULD be treated
as irreversible.* The function is gone from the standard. It appears nowhere in
`a8eec00`; the reference contract still has it, but the spec now describes the
Ouroboros loop as four manual steps ending in an ordinary ERC-721 transfer of
the token to its own TBA.

The note is retired as written, and what replaces it is not simply a rename:

- The **ordering constraint is now the spec's own**, stated as a critical
  requirement in the Ouroboros Loop section: configure the executor *before*
  transferring, or the being is permanently locked. That is the same hazard the
  July note was circling, promoted from an integrator footnote to normative
  guidance. Good.
- The **irreversibility claim is now doubtful.** It rested on there being no way
  to call out of a self-owning token's TBA. `executeOnBehalf()` is exactly such
  a way. If calls do originate from the TBA (§3.3, unresolved), then any holder
  of `EXECUTE_CALL` can have the TBA transfer the identity token back out, and
  self-ownership becomes reversible by a single executor key. That is a
  materially different security posture from the one the July note described,
  and the spec does not discuss it (defect D6).

Do not carry "self-ownership is irreversible" forward as a reassurance. Under
this interface it may be the opposite of reassuring.

---

## 7. Defects and gaps found in `a8eec00`

Reported, not fixed. Reopening a live standards submission is not an integrator's
call. Listed roughly by how much they cost someone building against the spec.

**D1 — The interface gives no safe authorization query.** `hasPermission()` is
absent, `getExecutorPermissions()` returns a bitmap that reads `0` for an
authorized owner under the reference implementation's fallback, and the spec
never documents that a fallback exists. An integrator following only the
standard will write authorization checks that reject legitimate callers. (§1.1)

**D2 — Recovery state is write-only.** `setRecoveryConfig()` has no getter, and
there is no `canTriggerRecovery()`. Combined with `getLastLiveness()` being
readable, an integrator gets one half of the comparison the standard describes
and cannot make the determination the mechanism exists to support. The reference
contract implements both. (§4.4)

**D3 — The digest rule for `contentHash` is self-contradictory and incomplete.**
The `anchor()` NatSpec calls `contentHash` the "Keccak256 hash of the content
being anchored" without qualification; the body text scopes the keccak
recommendation to `AnchorType.STATE` and never states a rule for
`AnchorType.ACTION`. Separately, whether an ACTION `contentHash` commits to the
artifact or to a manifest describing it is unstated, though the recommended
schema implies the latter. (§2.4, §2.5)

**D4 — The Reference Implementation section does not implement the specified
interface.** The spec cites `0x9fe33F0a1159395FBE93d16D695e7330831C8CfF` on Base
Sepolia and the `contracts/` sources in `Cyan-Society/Self-Owning-NFT`. Those
sources implement `anchorState()`, `getStateAnchor()`, `StateAnchored` and
`submitLivenessProof(uint256,bytes32)` — the superseded interface. They do not
implement `anchor()`, `getAnchor()`, `AnchorType`, `Anchored`,
`executeOnBehalf()`, or `submitLivenessProof(uint256,bytes)`. The ABI vendored
from that deployment and exercised in a live run by the Cyan Node prototype
confirms the deployed contract has the old shape. The "Demonstrated
Capabilities" transaction cited in the spec was an `anchorState()` call, and the
permission it names, `ANCHOR`, is `PERMISSION_ANCHOR_STATE` on that contract.
Nothing at that address implements what the spec specifies. This is the gap most
likely to be raised in review.

**D5 — `executeOnBehalf()` emits no event.** Every other state-changing function
in the interface has a corresponding event. Calls made on a being's behalf are
consequently unindexable from the identity contract, and — since Solidity return
data is not in a receipt — their results are unobservable after the fact.
Accountability is a stated goal of this standard; an unlogged arbitrary-call
primitive is in tension with it. (§3.2)

**D6 — `EXECUTE_CALL` is unbounded and undiscussed.** Bit 0 subsumes bit 4
`TRANSFER_ASSETS`, and plausibly permits moving the identity token out of its own
TBA, which would silently undo the Ouroboros loop. Security Considerations covers
executor *key* security thoroughly but never discusses executor *permission*
scope, and never notes that one bit can unwind self-ownership. (§3.4, §6)

**D7 — `executeOnBehalf()` semantics are underspecified.** Neither the
`msg.sender` observed by `target` nor the source of `value` is stated. Both are
load-bearing for any real integration. (§3.3)

**D8 — `requires: 165` with no interface identifier.** The front matter requires
ERC-165, but the document never defines an interface ID, never mentions
`supportsInterface`, and never says what a contract should return for it. There
is therefore no specified way to detect whether a contract implements ERC-8181 —
which is precisely what ERC-165 is for, and precisely what an indexer needs.

**D9 — One permission bit for two anchor types.** Not a contradiction, but a
design consequence of unifying `anchor()` that the Rationale does not address:
the standard's own least-privilege argument for the permission system is
weakened by a flag that cannot separate work attribution from cognitive-state
mutation. (§1.3)

---

## 8. Not about this interface

Three pitfalls from the source integration are recorded here only so readers of
the July notes know why they are absent above. They are properties of the
integration's own stack, unaffected by the interface revision, and documented in
`cyan-node/notes/`:

- **Route ordering.** A suffix route (`/papers/{id}.pdf`) must be declared before
  the bare path-parameter route, or the greedy `str` convertor captures `1.pdf`
  and the specific route is never reached.
- **SQLite across threads.** A connection opened in a synchronous dependency and
  used on the request thread needs `check_same_thread=False`, which is safe only
  while the node is single-worker and connections are not shared.
- **Digest choice as a project decision.** SHA-256 over Keccak is covered above
  in §2.4 as an interface matter; the *reason* — that independent verifiers can
  compute SHA-256 from a downloaded file with standard tooling — is a scholarly
  archiving argument, not a blockchain one.

---

## Change summary

| July 2026 item | Disposition | Where |
|---|---|---|
| Authorize via `hasPermission()`, never the raw bitmap | **revised** — hazard live, but `hasPermission()` is not in the standard | §1.1, D1 |
| `getStateAnchor()` returns only the latest; the tx is the record | **carried** — now per `(tokenId, AnchorType)`; conclusion unchanged | §2.2 |
| Only `tokenId` indexed; tx hash is the durable locator | **revised** — `anchorType` now indexed too; `contentHash` still is not | §2.3 |
| `stateHash` digest is application-defined; MUST document it | **revised** — still true; the spec language that acknowledged it was dropped | §2.4, D3 |
| `establishSelfOwnership()` is irreversible | **retired** — function gone from the standard; irreversibility now doubtful | §6, D6 |
| — | **new** — bit indices vs. bitmasks; `ANCHOR_STATE` renamed `ANCHOR` | §1.2 |
| — | **new** — one `ANCHOR` bit governs both anchor types | §1.3, D9 |
| — | **new** — `EXECUTE_CALL` is not a login signal | §1.4 |
| — | **new** — choose `AnchorType.ACTION` for a published work | §2.1 |
| — | **new** — decoding an indexed enum topic; topic0 changed | §2.3 |
| — | **new, unresolved** — ACTION `contentHash`: artifact or manifest? | §2.5, D3 |
| — | **new** — `executeOnBehalf()` return value invisible; no event | §3.2, D5 |
| — | **new, unresolved** — `msg.sender` and `value` semantics | §3.3, D7 |
| — | **new** — `EXECUTE_CALL` subsumes `TRANSFER_ASSETS` | §3.4, D6 |
| — | **new** — `bytes` attestation is expressible, not verified | §4.1 |
| — | **new** — attestation calldata and log-size cost | §4.2 |
| — | **carried** — `getLastLiveness()` conflates "never" with "at mint" | §4.3 |
| — | **carried** — recovery state is write-only | §4.4, D2 |
| — | **carried** — a CID is not a content digest | §2.6 |
| — | **carried** — the pinned record cannot name its own anchor | §2.7 |
| — | **revised** — one executor key serializes everything | §5.1 |
| — | **carried** — receipt-before-block race on public L2 RPC | §5.2 |
| — | **carried** — testnet anchors are never the canonical record | §5.3 |
