# Review and reproducibility status

## Exact reviewed packet identity

```text
ESTHER_RP001_v0_8_1_BLIND_REVIEW_PACKET.zip
SHA-256: 38288d2000a8295c8eb8bc540c3fab4491aa66b1dca60a4d45135a957e4834f6
```

That exact packet is not redistributed in this English-only public release because its review documents were produced in Russian. The English public review packet is a publication derivative, not the byte-identical blind-review input.

## Independent Windows reproduction

```text
PowerShell:                    7.5.8
Python:                        3.10.11
v0.8 tests:                    190/190
legacy v0.7 tests:             177/177
thread/process rounds:         100/20
source mutants:                16/16 killed
cross-analysis fixtures:       6/6
full-test negative control:    PASS
```

## Sixth blind model review

```text
Verdict: NO_CANDIDATE_BLOCKERS_FOUND
Candidate issues: 0
Confirmed defects: 0
```

Machine review is not human peer review. External human conceptual review, the endpoint-rater pilot, updated power analysis, registration, and the matched-control main study remain open.
