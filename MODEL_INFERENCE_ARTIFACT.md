# AlphaLens Model Inference Artifact

## Status and Scope

Model Packaging and Inference Artifact v1.0.0 packages the previously selected
Ridge Regression experiment for production inference. The authorized replay is
an engineering packaging operation, not model development, tuning, selection,
holdout evaluation, or experiment modification.

The packaging workflow may fit the exact approved Ridge and StandardScaler
pipeline once on the registered 611-observation final training window. After
packaging, production prediction services must load the immutable artifact and
must never invoke training.

## Artifact Contents

The immutable artifact contains:

- all twelve Ridge coefficients;
- Ridge intercept;
- all twelve StandardScaler means and scales;
- exact ordered feature schema and feature metadata;
- model dataset and final-training hashes;
- feature pipeline and target versions;
- selected experiment and holdout report provenance;
- source ingestion, feature, and target run identifiers;
- software versions;
- deterministic packaging configuration hash;
- deterministic numeric-state SHA-256;
- complete artifact SHA-256; and
- creation timestamp.

Every floating-point parameter is encoded with Python's IEEE-754 binary64
hexadecimal representation. This retains the exact fitted bit pattern rather
than rounding model state through decimal text.

## Production Inference Contract

`app.inference.artifact.PackagedRidgeInference` is the production inference
implementation. It:

- loads only verified artifact state;
- has no `fit` method;
- has no scikit-learn dependency;
- rejects artifact or state hash mismatches;
- enforces exact feature names, ordering, and vector length;
- rejects non-finite feature values and predictions; and
- exposes deterministic single-row, mapping, and batch prediction methods.

The loaded NumPy state arrays are read-only.

## Verification

Packaging verification loads the newly created artifact through the production
interface and reproduces the five already-recorded official holdout predictions
as exact `float.hex()` values. Their ordered prediction hash must equal the
official Holdout Evaluation Report prediction hash.

Verification stores every prediction timestamp, expected float value,
artifact-produced float value, source evidence hash, equality result, and an
immutable verification-evidence SHA-256. No holdout metric is recomputed.

Calling the packaging workflow after the artifact exists performs verification
and loading only; it returns the existing immutable artifact without fitting
again.
