# v0.8-E — Evidence, Reconciliation, and Reproducibility

## Mutation evidence

A mutant is classified as `KILLED` only when all of the following are present:

```text
passing baseline target
one named source diff
declared target execution
unique expected marker
nonzero mutated exit
```

An import, setup, or environment failure is `ERROR`, never `KILLED`.

## Reconciliation

The package uses the narrow `ReconciliationProposalRecord`. It preserves proposal and audit payloads and does not claim semantic merge validity.

## Full-test receipts

The runner executes the full pytest suites and saves JUnit XML, stdout, stderr, exit code, collected/executed/passed/failed/error/skipped counts, raw artifact SHA-256 values, and a receipt digest. Collection-only evidence cannot produce `PASS`.

## Windows runner

PowerShell uses named `$PyArgs`, not `$Args`. A disposable verifier performs a clean positive control and a failing-but-collectable negative control. Independent Windows Phase 1 completed with `PASS` under PowerShell 7.5.8 and Python 3.10.11.
