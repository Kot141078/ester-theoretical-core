# v0.8-C — SOC and Physical Authority Binding

## Typed SOC result

Domain actions and governance transitions are different tagged types. Every result belongs to a frozen universe and has its own hard-safety contract. Relevance cannot remove an admitted model from hard-safety evaluation.

## Immutable request identity

The first canonical digest is bound to `request_id` regardless of whether the outcome is accepted or rejected. An exact retry returns the earlier receipt. A changed digest is rejected before nonce claim or effect.

## Independent authority root

The effectful monitor uses two distinct objects:

```text
AuthorityDecision          - the specific decision
AuthorityPrefixSnapshot    - the independently trusted prefix root
```

The monitor checks snapshot integrity, closed cut, prefix digest, authority source, decision digest and status, request, capability, version, cut, and effect binding. A self-consistent decision from a foreign prefix is rejected as `AUTHORITY_PREFIX_MISMATCH`.

## SQLite transaction

The trusted prefix is stored in `meta` with its snapshot digest. `BEGIN IMMEDIATE` covers request identity, authority check, nonce, effect, receipt, and audit.

## Substrate boundary

A server-side operation registry defines effect class, budget, required scope, and instrument version. The caller cannot label an invasive operation passive. The quantum profile remains a mathematical and interface surface, not a claim of quantum agency.
