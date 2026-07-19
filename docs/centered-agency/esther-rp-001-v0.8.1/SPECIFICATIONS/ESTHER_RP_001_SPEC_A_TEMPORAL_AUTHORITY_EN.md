# v0.8-A — Temporal Authority Prefix and Atomic Cut

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

`commit_cut(cut, ())` declares that the complete authoritative cut is known and contains no occurrences. When `cut == next_cut`, it computes the canonical empty-batch digest, updates the prefix digest, publishes the closed cut, advances `next_cut`, and returns an empty decision tuple.

An exact retry is idempotent. A non-empty changed retry of the same cut is rejected without mutation.

## 3. Prefix rule

Cuts can be closed only in sequence. Arbitrary message arrival is allowed in the input buffer, but a durable decision is published only after prefix completeness has been established.

```text
revocation_cut <= invocation_cut -> REJECTED
invocation_cut < earliest_revocation_cut -> AUTHORIZED
```

## 4. Staged atomicity

Before publication, the implementation validates event and request identities, cut consistency, exact-retry digest, and collisions. Every projection is built in staged copies. An exception before publication leaves the original snapshot unchanged.

## 5. Trusted prefix snapshot

After a prefix is closed, the ledger emits:

```text
AuthorityPrefixSnapshot
    closed_cut
    closed_prefix_digest
    authority_source_id
    snapshot_digest
```

The snapshot is a separate trusted input to the physical monitor. An `AuthorityDecision` cannot authenticate its own prefix.

## 6. Bounded liveness

```text
declared ceiling:         8 ticks
observed worst-case path: 6 ticks
```

This is a finite model result, not an unbounded theorem.
