# AlphaLens OpportunityPlan V1.1 Hash-Provenance Exception

**Governance artifact version:** `1.0.0`
**Status:** Governance exception recorded; human acceptance required for Phase 9 use
**Scope:** Existing production OpportunityPlan V1.1 identity only

## 1. Purpose and boundary

This artifact records a historical provenance limitation for the active
OpportunityPlan V1.1 identity. It does not define, redesign, re-hash, replace,
or modify the OpportunityPlan policy. It does not approve Phase 9 performance
validation.

No production records, runtime behavior, configuration, thresholds, or
deployment are changed by this exception.

## 2. Proven production identity

The current production identity is:

- **Policy ID:** `alphalens_opportunity_plan_v1`
- **Version:** `1.1.0`
- **Existing runtime/persisted hash:**
  `145b25381be7912e3c363df5469e80fc1e1b9b64e787f07768c0feaee410a200`
- **Introducing commit:** `5366bf8de3590d13d7bec51ebe5329ead27ec`
- **Commit subject:** `fix(opportunities): use ATR for risk-distance instead of hardcoded 0.03%`

The current Phase 8 production dataset is homogeneous:

- 76/76 OutcomeRecords use V1.1;
- 0 records use V1.0; and
- 0 records have missing OpportunityPlan policy references.

The existing hash remains the authoritative persisted production identity for
these records. It must remain unchanged.

## 3. Proven implemented V1.1 behavior

The deployed implementation is proven to use:

- reference and entry price = `market_price_close`;
- risk distance = positive ATR true range;
- BUY invalidation = entry minus ATR;
- SELL invalidation = entry plus ATR;
- target distance = `1.5 × ATR`;
- validity horizon = `available_at + 10 minutes`;
- project `DECIMAL_QUANTUM` for decimal quantization; and
- plan result hashing through
  `canonical_sha256(plan, exclude={"result_hash"})`.

These statements document implemented behavior. They are not a reconstruction
of the historical policy-hash input.

## 4. Irrecoverable historical evidence

An exhaustive read-only repository and Git-history investigation searched all
available local and remote refs, tags, stashes, reflogs, reachable history,
unreachable objects, deleted or renamed files, introducing and later
OpportunityPlan commits, source, documentation, policy/hash helpers, and tests.

The following historical evidence was not recovered:

- original canonical V1.1 policy payload;
- original serialization rule for that payload;
- original hash-generation script or command;
- original reproducibility test vector;
- historical V1.1 policy artifact binding the payload to the hash; and
- an unambiguous Git object proving the payload-to-hash construction.

Accordingly, the original construction recipe for the existing V1.1 hash is
**irrecoverable from the available repository evidence**.

## 5. Prohibited actions

The following are not permitted under this exception:

1. Trial-generating or reverse-engineering a payload until it matches the
   existing digest.
2. Treating a newly invented payload or serialization as historical truth.
3. Generating or recording a replacement canonical hash.
4. Modifying V1.1 runtime behavior to repair historical provenance.
5. Modifying, inserting, deleting, or rewriting production records.
6. Treating this exception as evidence of predictive performance,
   profitability, or Phase 9 readiness.

## 6. Historical V1.0 preservation

`ALPHALENS_V2_OPPORTUNITY_PLAN_POLICY_V1.md`, version `1.0.0`, remains the
historical/frozen V1.0 artifact. It is preserved unchanged and is not the
active policy for the current 76-record production dataset.

## 7. Phase 9 implication

The existing V1.1 policy identity may be referenced as a frozen Phase 9
dependency only if a human Phase 9 approver explicitly accepts the following
limitation:

> The active production policy identity is known and consistently persisted,
> but its original historical hash-construction provenance is irrecoverable
> from the available repository evidence.

This artifact does not grant that acceptance and does not silently approve the
Phase 9 methodology or performance validation.

## 8. Human decision required

**HUMAN DECISION REQUIRED:**

> Accept existing V1.1 policy identity with irrecoverable historical
> hash-construction provenance as a frozen Phase 9 dependency.

Until this decision is explicitly recorded, Phase 9 performance evaluation must
not proceed. All other unresolved Phase 9 methodology decisions remain
unchanged.
