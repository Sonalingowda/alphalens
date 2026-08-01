# AlphaLens v2 Explainability Mathematics Research Specification

**Version:** Research Specification v1.0.0

**Status:** Policy-neutral research specification; no template set is approved

## 1. Scope

This specification defines a deterministic, evidence-preserving transformation
from quantitative artifacts to human-readable reasoning. Explanation is a
projection. It SHALL NOT create evidence, interpretation, score, confidence,
causality, or advice.

## 2. Symbols and Traceability

Let (E=(e_1,\ldots,e_n)) be an immutable Evidence Package, (P) a complete
policy trace, (\Lambda) limitations, and (\mathcal T_v) a versioned template
set. An explanation is

\[
Y=\mathcal G(E,P,\Lambda;\mathcal T_v,locale).
\]

Each sentence (y_j) has an evidence-support set
(\mu(y_j)\subseteq E\cup P\cup\Lambda). The traceability invariant is

\[
\forall y_j,\ \mu(y_j)\ne\varnothing,
\]

and every factual numeric binding must equal its source after canonical locale
formatting. A sentence with no support is invalid.

## 3. Evidence and Importance Ordering

Sections follow the frozen order: assessment/scope, support, contradiction,
context/data quality, optional plan, authorized confidence, freshness/lifecycle,
then limitations/disclosure.

Within a section, the default complete key is

\[
K_E(e)=(category\_ordinal,policy\_predicate\_ordinal,a_e,
source\_id,evidence\_id).
\]

An importance order MAY replace or extend this key only through an approved
policy trace. Possible research variables include gate role, disqualifying
authority, component contribution, and material limitation, but no priority,
weight, or severity order is selected here. Score magnitude alone SHALL NOT
silence contradiction.

## 4. Contradiction and Coverage

Let (E^+,E^-,E^0) be polarity partitions for the explained proposition.
Supporting and contradicting sections SHALL each include every material item
required by the active policy. Contradictions may be summarized only if the
summary retains a one-to-many evidence mapping and no distinct qualification is
lost. A coverage audit records

\[
\operatorname{Covered}(E_R,Y)=
\{e\in E_R:\exists y_j, e\in\mu(y_j)\},
\]

where (E_R) is the policy-required explainable subset. Validity requires
(\operatorname{Covered}(E_R,Y)=E_R).

## 5. Deterministic Generation

Templates are immutable functions of typed bindings. Canonical generation
requires fixed template identity/version, locale, number and timestamp format,
enum vocabulary, omission rules, pluralization, section order, and evidence
order. For identical inputs,

\[
\mathcal G(E,P,\Lambda;\mathcal T_v,l)
=\mathcal G(E,P,\Lambda;\mathcal T_v,l)
\]

byte for byte. Free-form generated prose is noncanonical and cannot replace the
verified artifact.

## 6. Required Disclosures and Neutrality

Every published explanation states that AlphaLens identified an opportunity
from recorded evidence, does not guarantee outcomes, does not execute trades,
and leaves the decision to the user. It discloses material contradiction,
missing/stale evidence, proxy limitations, unavailable confidence, and scope
limits.

Neutral relations include “was observed,” “is consistent with,” “supports,”
“contradicts,” and “was unavailable,” only when the evidence relation supports
them. `SELL` means a downward opportunity and never exit.

## 7. Forbidden Wording

Canonical explanations SHALL NOT assert future certainty, guaranteed profit,
causality without causal evidence, safety, execution, personalized advice,
position size, or hidden probability. “Will rise,” “will fall,” “guaranteed,”
“safe trade,” “certain,” and “execute” are forbidden implications. Confidence,
probability, percentages, or qualitative confidence labels require a separately
authorized calibrated record.

## 8. Assumptions and Dependencies

Explanation depends on verified Evidence Packages, policy traces, assessment,
lifecycle, optional plan, and optional authorized confidence. It assumes the
taxonomy and templates provide total mappings for every required reason and
limitation code.

## 9. Validation and Future Research

Validation SHALL prove sentence support, value equality, contradiction and
limitation coverage, forbidden-language absence, deterministic ordering,
future isolation, locale reproducibility, and stable hashes. Phase 5B MAY test
human comprehension and calibration of interpretation through preregistered
studies, but readability results SHALL NOT authorize unsupported claims or
alter quantitative evidence.
