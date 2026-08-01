# AlphaLens v2 Explainability Contract

**Contract version:** `1.0.0`
**Status:** Final architecture specification

## 1. Purpose and Source of Truth

The Explanation Engine SHALL transform verified Evidence Taxonomy records and
policy traces into deterministic, factual language. Evidence remains the source
of truth. Explanation SHALL NOT create evidence, decisions, scores, confidence,
causal claims, or quantitative interpretations.

## 2. Explanation Artifact

Every artifact MUST contain explanation identity/version, opportunity revision,
language/locale, taxonomy and template-set versions, evidence cutoff,
generated-at, ordered sections, sentence-to-evidence mappings, limitations,
configuration/code identities, and result hash.

Every sentence MUST contain a stable template identifier, bound typed values,
ordered evidence references, and resulting rendered text. Free-form generative
text SHALL NOT be canonical. An AI-generated optional presentation MAY exist
only as a non-authoritative derivative that is separately labeled and verified
against the canonical artifact.

## 3. Required Sections and Ordering

Sections SHALL appear in this order when applicable:

1. assessed opportunity and scope;
2. supporting evidence;
3. contradicting evidence;
4. market and data-quality context;
5. opportunity plan, when present;
6. confidence, only when authorized;
7. freshness and lifecycle;
8. limitations and user-decision disclosure.

Within each section, evidence SHALL follow taxonomy category order, policy
predicate order, source availability, and evidence identity. Supporting
evidence SHALL NOT suppress contradicting evidence.

## 4. Sentence Generation Rules

Templates MUST be versioned, immutable, neutral, grammatically complete, and
bound only to validated typed values. Numeric formatting, units, timestamps,
enum labels, pluralization, and omission rules MUST be canonical per locale.
Missing optional evidence SHALL produce a sentence only when its absence is a
material limitation. Repeated facts SHOULD be coalesced only by an approved
template rule preserving all evidence references.

## 5. Required Disclosures

Every published explanation MUST state that AlphaLens identified an
opportunity from recorded evidence, does not guarantee outcomes, does not
execute trades, and leaves the decision to the user. It MUST disclose stale or
partial evidence, unavailable confidence, material contradictions, proxy data,
and known scope limitations where applicable.

## 6. Forbidden Wording

Explanations SHALL NOT use wording that asserts certainty, guaranteed profit,
causality without causal evidence, execution, personalized advice, position
size, or hidden confidence. Prohibited implications include “will rise,” “will
fall,” “guaranteed,” “safe trade,” “certain,” “execute,” and using `SELL` to
mean exit. Words such as “confidence,” “probability,” or percentages SHALL
appear only when an authorized Confidence Contract record supports them.

## 7. Neutral and Uncertainty Wording

Evidence statements SHOULD use forms such as “is consistent with,” “supports,”
“contradicts,” “was observed,” and “was unavailable.” Uncertainty SHALL be
expressed through recorded limitations and contradicting evidence, not invented
hedging scales. Score SHALL be named opportunity score; rank SHALL be named
relative rank; neither SHALL be called confidence.

## 8. Reproducibility and Validation

The same artifact inputs, template set, locale, and formatting configuration
MUST produce byte-identical canonical text and hash. Validation MUST prove every
claim maps to evidence, every displayed value equals its source, required
sections/disclosures are present, forbidden language is absent, ordering is
stable, and no evidence exceeds the cutoff. Template changes require a new
version and SHALL NOT rewrite prior explanations.
