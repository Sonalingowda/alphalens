# AlphaLens Frozen Conceptual Architecture

## Status

This document records the approved conceptual architecture for AlphaLens. The architecture is frozen and must not be redesigned during implementation. Implementation must follow architecture.

Implementation details are intentionally excluded. They may be documented only within a future phase after that phase receives explicit human approval.

## Conceptual System

```text
Presentation Layer
        ↓
API Layer
        ↓
Research Layer
        ↓
Feature Engineering Layer
        ↓
Data Layer
        ↓
External Market Data Providers
```

### Presentation Layer

Presents research workflows, results, evidence, limitations, and provenance to users. It is responsible for clear interaction and communication, not for redefining research logic.

### API Layer

Provides the controlled boundary between presentation concerns and the platform's research capabilities. It exposes approved operations and results while preserving validation, traceability, and layer separation.

### Research Layer

Coordinates quantitative research, chronological validation, experiments, evaluation, benchmarking, and reproducible reporting under the rules in `RESEARCH_CONSTITUTION.md`.

### Feature Engineering Layer

Defines and produces research features from information available at the applicable point in time. It preserves feature definitions and guards against leakage between data and research concerns.

### Data Layer

Acquires, validates, versions, stores, and retrieves market data and its provenance. It provides point-in-time data access required for auditable and reproducible research.

### External Market Data Providers

Supply external market information to AlphaLens. Provider data is an input whose source, availability, revisions, and limitations must remain identifiable.

## Approved Technology Stack — Future Implementation Reference

The approved technology stack for future, explicitly authorized implementation phases is:

- Python
- FastAPI
- Next.js
- TypeScript
- PostgreSQL
- scikit-learn
- XGBoost
- LightGBM
- TradingView Lightweight Charts
- Git
- GitHub
- VS Code

This list is reference information only. It does not authorize implementation, dependency installation, framework configuration, scaffolding, or changes to the conceptual architecture.

## Reserved for Future Approved Phases

The following sections are intentionally reserved as placeholders. They contain no design and confer no implementation authority.

### Phase 1 — Project Structure & Scaffolding

To be documented only after explicit human approval.

### Phase 2 — Data Ingestion Foundations

To be documented only after explicit human approval.

### Phase 3 — Feature Engineering

To be documented only after explicit human approval.

### Phase 4 — Validation Framework

To be documented only after explicit human approval.

### Phase 5 — API Layer

To be documented only after explicit human approval.

### Phase 6 — Presentation Layer

To be documented only after explicit human approval.

### Phase 7 — Reporting & Explainability

To be documented only after explicit human approval.
