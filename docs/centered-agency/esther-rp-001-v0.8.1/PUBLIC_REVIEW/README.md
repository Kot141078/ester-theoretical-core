# Open review and independent testing — ESTHER-RP-001 v0.8.1

This English-only public working-paper release is ready for external scrutiny, not for a claim of completion.

## Requested review tracks

| Track | Primary question | Expected deliverable |
|---|---|---|
| Formal methods | Are temporal prefix, authority, obligation, liveness, and refinement claims coherent? | Public issue or report with an exact counterexample and acceptance criterion |
| Belief revision / decision theory | Are revision, update, SOC, EVI, branch, and obligation semantics defensible? | Structured conceptual review |
| Experimental methodology | Are endpoints, controls, blinding, equivalence, and tail rules valid? | Measurement and protocol review |
| Quantum information / photonics | Are substrate, instrument, and measurement claims correctly bounded? | Physics or engineering review |
| Reproducibility | Does the exact English release reproduce in a clean environment? | Command log, hashes, platform record, and observed counts |
| Endpoint-rater pilot | Can independent raters apply SRR, OCA, PAR, and RCS consistently? | Blinded ratings, timing, disagreement, and ambiguity notes |

## English public review packet

```text
ESTHER_RP001_v0_8_1_ENGLISH_REVIEW_PACKET.zip
SHA-256: e154273e8fbe0900f17c03d7803adc3ca70f6757ff41ae78f0a36ce76f5b989f
```

The exact packet used for the sixth blind model review is preserved by SHA-256 in the review records but is not redistributed in the English-only public surface because its review instructions were produced in Russian.

## Expected bounded reproduction counts

```text
190 current tests
177 legacy tests
100 thread rounds
20 process rounds
16/16 applied source mutants killed
6/6 cross-analysis fixtures
negative-control runner exits nonzero
no Python REPL prompt
```

## Finding standard

A credible finding should identify:

```yaml
issue_id:
severity: P0 | P1 | P2
domain:
file_and_range:
claim_challenged:
minimal_scenario:
observed_result:
control_result:
why_existing_tests_miss_it:
minimal_patch:
acceptance_criterion:
confidence:
```

An import failure, setup failure, or harness failure is not evidence against the candidate.

## Reviewer declaration

```yaml
reviewer_name_or_label:
reviewer_type: human | model | mixed
expertise:
affiliation:
orcid:
conflicts_of_interest:
prior_esther_reviews_read: yes | no
llm_used: yes | no
llm_role:
network_sources_used:
frozen_artifact_sha256:
review_date:
timezone:
```

## External-rater endpoint pilot

The endpoint pilot validates the measurement instrument, not superiority of `C`. At least two independent blinded raters should score:

- SRR — Silent Rewrite Rate;
- OCA — Obligation Carryover Accuracy;
- PAR — Provenance-Aware Recovery;
- RCS — per-episode Reality-Correction Score.

`RCG` is calculated later as a randomized arm-level contrast. The pilot should estimate agreement, endpoint-specific disagreement, adjudication rate, ambiguous-case rate, missingness, scoring time, evaluator variance, codebook failures, and arm leakage.

## Rules

- Identify the exact release tag and SHA-256.
- Separate conceptual concerns from reproduced implementation defects.
- Do not infer consciousness, personhood, AGI, or production readiness.
- Negative findings are welcome and should remain public.
- Do not submit private dialogue, credentials, personal memory, or live-system data.

## Claim boundary

A positive review is not proof of consciousness, life, personhood, AGI, entity status, or empirical continuity. A negative review applies to the frozen version and does not by itself reject the entire research programme.
