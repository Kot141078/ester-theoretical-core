# v0.8-B - Obligation and Evidence Lifecycle

This surface is carried forward from `v0.7` without weakening.

## Obligation creation

Public creation accepts only a canonical `CREATED` token with empty transition, evidence, lineage, and escalation fields.

## Normative debtor and operational handler

```text
normative_debtor
operational_handler
```

Escalation changes the handler. The normative debtor changes only through an atomic transfer with an authority request, evidence, named acceptance, and a repository-issued successor.

## Evidence identity

```text
evidence_id -> immutable content digest
current_status -> exactly one value
transition_history -> append-only
```

`ACCEPTED`, `PROVISIONAL`, `CONTESTED`, `QUARANTINED`, and `REJECTED` remain distinct. Claim aggregation is separate from evidence identity state.

## Acceptance criteria

```text
dirty or terminal creation is rejected
escalation does not release the debtor
transfer preserves normative lineage
changed content under one evidence ID is rejected
one current status exists per evidence item
```
