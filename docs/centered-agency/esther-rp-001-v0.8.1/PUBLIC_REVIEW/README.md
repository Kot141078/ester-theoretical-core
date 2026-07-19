# Public review and independent testing

## Open call

`ESTHER-RP-001 v0.8.1 — Centered Agency Under Persistent Uncertainty` is published as a public preprint and bounded executable research package.

This is not a machine-consciousness claim. The release asks what a persistent system must preserve in order to maintain unresolved world-models, make local commitments, revise itself without rewriting history, and remain accountable for authority, obligations, and physical consequences.

## Reviewers sought

1. **Formal methods / distributed systems** — causal prefix, atomic publication, replay/fork/succession, safety/liveness/refinement.
2. **Belief revision / decision theory** — revision versus world update, evidence status, obligations, SOC, multiple priors, and stopping.
3. **Experimental methodology** — construct validity, information parity, SRR/OCA/PAR/RCS, equivalence margins, hierarchical design, endpoint gaming.
4. **Quantum information / photonics** — measurement instruments, basis/reference dependence, calibration/noise, classical coherent versus quantum photonics, and the boundary between hardware capability and agency claims.

## Frozen target

```text
ESTHER_RP001_v0_8_1_BLIND_REVIEW_PACKET.zip
SHA-256:
38288d2000a8295c8eb8bc540c3fab4491aa66b1dca60a4d45135a957e4834f6
```

The frozen ZIP is attached to the versioned GitHub release and Zenodo record.

## Windows reproduction

```powershell
.\RUN_ALL_V08.ps1 -PythonExe 'C:\Python310\python.exe'

.\TOOLS\VERIFY_WINDOWS_RUNNER_V08.ps1 `
  -PythonExe 'C:\Python310\python.exe'
```

Expected bounded counts:

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

## Claim boundary

A positive review is not proof of consciousness, life, personhood, AGI, entity status, or empirical continuity. A negative review applies to the frozen version and does not by itself reject the entire research programme.
