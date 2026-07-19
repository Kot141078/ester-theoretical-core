# v0.8-A - Temporal Authority Prefix and Atomic Cut

## 1. State

```text
next_cut
closed_prefix_watermark
closed_prefix_digest
authority_source_id
raw_events
closed_cuts
request_decisions
earliest_revocation_by_capability
audit
```

## 2. Explicit empty cut

`commit_cut(cut, ())` declares that the complete authoritative cut is known and contains no occurrences. When `cut == next_cut`, it:

1. computes the canonical empty-batch digest;
2. updates the prefix digest;
3. publishes the closed cut;
4. advances `next_cut`;
5. returns an empty decision tuple.

An exact retry is idempotent. A changed non-empty retry for the same cut is rejected without mutation.

## 3. Prefix rule

Cuts may be closed only sequentially. Arbitrary message arrival is permitted in the input buffer, but a durable decision is published only after prefix completeness has been established.

```text
revocation_cut <= invocation_cut -> REJECTED
invocation_cut < earliest_revocation_cut -> AUTHORIZED
```

## 4. Staged atomicity

Before publication, the implementation validates event and request identities, cut consistency, exact-retry digest, and collisions. All projections are built in staged copies. An exception before publication leaves the original snapshot unchanged.

## 5. Trusted prefix snapshot

After closing a prefix, the ledger emits:

```text
AuthorityPrefixSnapshot
    closed_cut
    closed_prefix_digest
    authority_source_id
    snapshot_digest
```

The snapshot is a separate trusted prerequisite for the physical monitor. An `AuthorityDecision` cannot validate its own prefix.

## 6. Bounded liveness

```text
declared ceiling:         8 ticks
observed worst-case path: 6 ticks
```

This is a finite-model result, not an unbounded theorem.

## 7. Acceptance criteria

```text
empty cut closes prefix
empty retry is idempotent
changed retry causes no mutation
out-of-order cut is rejected
failed cut leaves state unchanged
foreign prefix is rejected by the monitor
mutants M14/M15 are killed
```
