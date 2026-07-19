# v0.8-B — Obligation and Evidence Lifecycle

Public creation accepts only a canonical `CREATED` token with empty transition, evidence, lineage, and escalation fields.

## Normative debtor and handler

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

The statuses `ACCEPTED`, `PROVISIONAL`, `CONTESTED`, `QUARANTINED`, and `REJECTED` remain distinct. Claim aggregation is separate from identity state.
