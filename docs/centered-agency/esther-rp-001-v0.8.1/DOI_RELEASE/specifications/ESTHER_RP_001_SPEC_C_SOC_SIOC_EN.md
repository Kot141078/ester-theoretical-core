# v0.8-C - SOC and Physical Authority Binding

## 1. Typed SOC result

Domain actions and governance transitions are different tagged types. Every result belongs to a frozen universe and has its own hard-safety contract. Relevance cannot remove an admitted model from hard-safety evaluation.

## 2. Immutable request identity

The first canonical digest is bound to `request_id` regardless of whether the outcome is accepted or rejected. An exact retry returns the prior receipt. A changed digest is rejected before nonce claim or effect.

## 3. Independent authority root

The effectful monitor uses two different objects:

```text
AuthorityDecision          - concrete decision
AuthorityPrefixSnapshot    - independently trusted prefix root
```

It validates:

```text
snapshot integrity
snapshot closed cut
snapshot prefix digest
snapshot authority source
decision digest and status
request/capability/version/cut/effect binding
```

A self-consistent decision from a foreign prefix is rejected as `AUTHORITY_PREFIX_MISMATCH`.

## 4. SQLite transaction

The trusted prefix is stored in `meta` with its snapshot digest. `BEGIN IMMEDIATE` covers request identity, authority check, nonce, effect, receipt, and audit.

## 5. Substrate boundary

A server-side operation registry determines effect class, budget, required scope, and instrument version. The caller cannot label an invasive operation as passive. The quantum profile remains a mathematical and interface surface, not a quantum-agency claim.

## 6. Acceptance criteria

```text
missing prefix -> zero effect
foreign prefix -> zero effect
matching prefix and decision -> one effect
meta prefix tampering is detected
rejected-first request cannot be rebound
the same nonce creates one effect under contention
```
