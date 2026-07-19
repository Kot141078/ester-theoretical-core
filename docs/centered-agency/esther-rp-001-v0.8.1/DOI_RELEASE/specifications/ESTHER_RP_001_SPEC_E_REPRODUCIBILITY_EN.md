# v0.8-E - Evidence, Reconciliation, and Reproducibility

## Mutation evidence

A mutant is counted as `KILLED` only when all of the following hold:

```text
passing baseline target
one named source diff
declared target execution
unique expected marker
non-zero mutated exit
```

An import, setup, or environment failure is `ERROR`. Version `v0.8` contains sixteen mutants, including empty-cut, prefix-binding, and full-test-receipt bypasses.

## Reconciliation

The narrow `ReconciliationProposalRecord` is used. It preserves proposal and audit payloads and does not claim semantic merge validity.

## Full-test receipts

The runner executes the full pytest suite and stores:

```text
JUnit XML
stdout
stderr
exit code
collected/executed/passed/failed/error/skipped counts
raw SHA-256 artifacts
receipt digest
```

The finaliser rechecks receipts, counts, paths, and hashes. Collection-only mode cannot produce `PASS`. Changing an evidence artifact after execution invalidates the report.

## Windows runner

PowerShell uses named `$PyArgs`, not the automatic `$Args`. The disposable verifier runs a clean positive control and a failing-but-collectable negative control. Independent Windows Phase 1 completed with `PASS` under PowerShell 7.5.8 and Python 3.10.11.

## Acceptance criteria

```text
16/16 target mutants are killed
unrelated failure -> ERROR
clean full suites -> PASS
failing-but-collectable suite -> non-zero/FAIL
artifact tampering -> receipt verification FAIL
no REPL prompt in the Windows positive control
```
