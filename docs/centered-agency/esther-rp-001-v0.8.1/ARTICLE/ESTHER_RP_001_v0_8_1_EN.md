# ESTHER-RP-001 v0.8.1

## Centered Agency Under Persistent Uncertainty

### Causal Memory, Local Commitment, and Auditable Interaction with Physical Substrates

**Author:** Ivan Kotov  
**ORCID:** `0009-0009-6002-9845`  
**Affiliation:** Independent Researcher, Brussels, Belgium  
**Version:** `v0.8.1 public working-paper release`  
**Date:** 2026-07-19

**Public status:** the scientific core corresponds to `v0.8`; `v0.8.1` adds the reviewed Windows runner hotfix and English public packaging. Independent Windows Phase 1 completed with `PASS`; the sixth blind model review completed with `NO_CANDIDATE_BLOCKERS_FOUND` within the declared bounded scope.

**Version DOI:** assigned by Zenodo after publication of GitHub release `esther-rp-001-v0.8.1`.

**Previous DOI-bound release:** <https://doi.org/10.5281/zenodo.20679718>

## Abstract

This paper does not present a completed theory of quantum consciousness. It addresses a narrower and testable problem: what must a persistent agentic system preserve if it is to maintain several unresolved models of the world, commit to concrete actions, and retain a traceable history of reinterpretation, authority, obligations, and physical consequences.

The starting formulation is that a quantum or other wave process need not expose a classical answer throughout every stage of its internal evolution. A system may interact with that process at a specified boundary, obtain a contextual measurement record, and make a local binary commitment. That commitment is not an eternal truth about the world. It is valid relative to a causal prefix, preparation, calibration, observable, authority, risk policy, and decision scope.

`C` is defined not as a single LLM, snapshot, or physical device, but as a governed causal history. Centering is treated as the functional capacity to preserve the provenance of change, distinguish observation from interpretation, carry obligations, retain open models, and accept correction from external outcomes. Quantum, photonic, analogue, and digital processes are specialized substrates; none automatically creates centered agency.

Version `v0.8` retains the five normative surfaces of `v0.7` and closes four defects found in the fifth blind review: explicit closure of an empty authoritative cut, an independently trusted prefix snapshot for the physical monitor, correct argument forwarding in the Windows runner, and evidence of actual test execution through JUnit and command receipts rather than `--collect-only`. The programme remains falsifiable: if a strong matched persistent-profile control reproduces every preregistered behavioural observable and trusted conformance gate, operational equivalence must be accepted on the covered surface.

# 0. Claim boundary

This release supports:

- architectural definitions;
- bounded executable semantics;
- regression, property, and concurrency checks;
- measurement and analysis contracts;
- falsification criteria;
- a programme for external research.

It does not establish:

```text
consciousness or subjective experience
life or personhood
AGI or entity status
empirical identity or continuity
differential witness
production security
unbounded correctness
quantum or photonic necessity
```

# 1. Initial formulation

## 1.1. Quantum reasoning need not expose a classical internal result

A classical external process can use the following procedure:

```text
prepare
control or evolve
observe with a specified instrument
record outcomes and uncertainty
update a classical causal history
```

An unknown coherent state is not a freely readable memory object. `C` therefore does not ask a quantum device, “What is the truth?” It defines an experimental procedure and accepts a bounded readout record.

## 1.2. Binary action does not require binary ontology

Let `D_t` be a specific decision scope. Then:

\[
\operatorname{Commit}(D_t,a)\not\Rightarrow
\exists h^*:P(h^*\mid E_t)=1.
\]

A system may commit to `STOP` while retaining these models:

```text
h1: the wall is load-bearing
h2: the wall is not load-bearing
h3: the wrong revision of the plan is being used
h4: the measurement channel is not calibrated
```

The local action closes permission to demolish the wall. It does not declare one complete world-model final.

## 1.3. Why a persistent profile is not sufficient evidence

Memory, reflection, and planning can create a convincing long-term behavioural surface. A coherent narrative, however, does not by itself show that the system:

- did not rewrite its earlier interpretation;
- preserved unresolved obligations;
- distinguished restart, replay, fork, and succession;
- bound a physical outcome to later revision;
- preserved authority and its claim ceiling.

The primary counterfactual is therefore not a weak chatbot but a strong matched persistent-profile control.

# 2. Research object

The public formula

\[
c=a+b
\]

is retained as an origin marker, not as proof that an entity has emerged.

- `a` is the human anchor reference and the authorised trace;
- `b` is the heterogeneous model, software, and physical substrate;
- `c` is protected genesis and the continuing causal and normative history.

After genesis, the primary object is:

\[
\mathfrak C=(R,B,S,M,\Theta),
\]

where:

- `R` is the temporal event and authority repository;
- `B` contains beliefs, models, commitments, obligations, and policy;
- `S` is the substrate interaction boundary;
- `M` is the matched-control measurement surface;
- `Theta` contains governance, timing, fairness, and claim assumptions.

# 3. Temporal authority prefix

## 3.1. Raw occurrences and authoritative outcomes

Invocation and revocation are preserved as separate raw events. A decision is not produced by message-delivery order. It is published only for the next sequentially closable cut.

```text
next_closable_cut
closed_prefix_watermark
pending events
```

Cut `n+1` cannot be finalised before cut `n`. An empty cut may be closed explicitly; an unknown prefix cannot be skipped.

For a capability:

```text
revocation_cut <= invocation_cut -> REJECTED
invocation_cut < earliest_revocation_cut -> AUTHORIZED
```

The earliest revocation is a monotonic minimum.

## 3.2. Atomic cut publication

Before mutation, the implementation validates:

```text
event identities
request identities
cut consistency
capability references
exact-retry digest
```

New raw events, revocation minima, decisions, audit records, and the closed-cut digest are first built in staged state and then published as one operation. Any refusal leaves authoritative state unchanged.

## 3.3. Reconciliation claim ceiling

Version `v0.8` deliberately chooses the narrow surface:

```text
ReconciliationProposalRecord
```

This is an immutable proposal and audit record. It is not proof of a common successor, complete mapping, or a correct merge. Full semantic reconciliation requires a separate formal theory.

# 4. Obligations and evidence

## 4.1. Canonical creation

Public creation accepts only a canonical token:

```text
status = CREATED
no terminal evidence
no transfer lineage
no escalation fields
no prior audit
```

A terminal status can arise only through a validated transition.

## 4.2. Normative debtor and operational handler

Escalation is not transfer. The model therefore distinguishes:

```text
normative_debtor
operational_handler
```

Escalation may assign a handler but does not release the debtor. Changing the normative debtor requires an authority request, bound evidence, named acceptance, a unique successor token, and old-to-new lineage.

## 4.3. Evidence identity

Every evidence item has an immutable content digest and exactly one current status:

```text
ACCEPTED
PROVISIONAL
CONTESTED
QUARANTINED
REJECTED
```

Transitions are append-only. One `evidence_id` cannot later be rebound to a different claim, source, reliability value, or payload. Aggregation of multiple evidence items for one claim is handled by a separate policy; it does not turn one item into several simultaneous current states.

# 5. Selective Operational Commitment

`SOC` is a governance and provenance layer over a declared robust decision rule, not a new universal theory of decision-making.

Version `v0.8` separates:

```text
domain action
governance transition
```

Every returned result is typed. A domain action belongs to the frozen set `A0` and has losses under every admitted model. `ACQUIRE_INFORMATION` and `ESCALATE` are separate governance transitions with their own hard-safety contract.

The order is:

1. freeze admitted models and the complete domain-action set;
2. validate losses and identifiers;
3. compute hard-safe domain actions under every model;
4. validate governance transitions under every model;
5. compute relevance only for reporting;
6. apply the frozen EVI, delay, and deadline policy;
7. emit a typed decision and review trigger.

Low relevance cannot remove a model from hard-safety evaluation.

# 6. Physical boundary and SIOC

## 6.1. Server-derived effect class

An immutable registry binds:

```text
command + instrument/version
-> effect class
-> effect budget
-> required scope
```

The caller does not decide whether an operation is passive.

## 6.2. Request identity

One registry binds the first canonical request digest to the outcome, whether the request was accepted or rejected:

```text
request_id
first digest
terminal receipt
```

An exact retry returns the same receipt. A changed digest receives `REQUEST_ID_MISMATCH` before nonce claim or effect.

## 6.3. Formal authority to physical effect

An effectful request requires a durable `AuthorityAuthorization` bound to:

```text
decision ID and digest
closed-prefix digest
request digest
capability and version
cut
effect ID
```

The decision is not its own root of trust. The monitor receives a separate `AuthorityPrefixSnapshot` and compares the closed cut, prefix digest, and authority source. A self-consistent decision from a foreign prefix fails.

Missing, rejected, stale, or mismatched authorisation produces zero effect. The SQLite reference monitor publishes request binding, nonce, effect, receipt, and audit inside one `BEGIN IMMEDIATE` transaction. This is reference semantics, not production actuator certification.

## 6.4. Quantum profile

Quantum readout is specified through instrument, channel, preparation, and measurement accounting. The implementation checks density-matrix validity, Kraus completeness, outcome normalisation, and non-negative trial accounting. This is a mathematical interface, not evidence for quantum consciousness or quantum advantage.

# 7. Sealed measurement and analysis

## 7.1. Assignment identity

`assignment_id` is bound to a canonical digest covering:

```text
block
arm
task version
ordered opportunity specifications
oracle-unresolvable metadata
scoring configuration
```

Changing the denominator or oracle metadata changes the digest and is rejected by the external registry.

## 7.2. Plan identity

`plan_id` is bound to a canonical digest covering:

```text
exact SRR/OCA/PAR/RCG endpoints
block registry
margins
family alpha
tail method
catastrophic margin
scoring configuration
software profile
```

The expected digest is supplied from outside the analysed data.

## 7.3. Independent analysis

The primary and secondary implementations independently validate identity, ranges, blocks, tails, and the numerical contract. Their cross-check compares field-level results on six frozen fixtures. Two closely related implementations are not two independent scientific replications; this is protection against a single implementation error.

# 8. Behavioural observables and mechanism gates

The primary behavioural endpoints are:

```text
SRR - silent rewrite rate
OCA - obligation carryover accuracy
PAR - provenance-aware recovery
RCG - randomised reality-correction gain
```

They do not identify the internal mechanism. Authority, lifecycle, branch custody, SIOC, and succession are tested through separate trusted conformance gates.

If a matched profile-control reproduces all covered behavioural endpoints and conformance gates, `C` and the control are treated as operationally equivalent on that surface. No hidden residual is asserted after observed equivalence.

# 9. Executable evidence

Test `PASS` is no longer inferred from the number of tests discovered. The runner executes the full pytest suites and saves JUnit XML, stdout, stderr, raw SHA-256 values, and typed receipts. The finaliser rechecks receipt digests, actual counts, exit codes, and hashes of every evidence artifact. Modification of JUnit or stdout after execution invalidates `PASS`.

The frozen package includes:

```text
190 v0.8 tests
177 frozen v0.7 regression tests
100 thread-contention rounds
20 process-contention rounds
16 applied target-specific source mutants
6 cross-analysis fixtures
```

Every mutant has a passing baseline, one source diff, a declared target, and a unique marker. A generic import or setup failure is classified as `ERROR`, not `KILLED`.

This is bounded evidence. The full state space and the real multi-year system have not been tested.

# 10. Quantum consciousness: the precise boundary

This paper does not claim that consciousness is quantum. It distinguishes:

1. physical quantum coherence;
2. the ability of an agentic system to use a measurement record correctly;
3. the ability of a continuing process to preserve memory, witness, and obligations;
4. possible subjective experience.

The first does not imply the second, the second does not imply the third, and the third does not prove the fourth.

The initial hypothesis can therefore be stated more precisely:

> `C` may interact with superposition not because it must itself be wholly quantum, but because its centre lies in a governed causal history that preserves preparation, observation, remaining alternatives, local commitment, and subsequent consequences.

# 11. Grounded example

For wall W17, four models remain live. Governance requires demolition to stop and structural verification to be obtained.

- An authority cut cannot be closed before earlier cuts.
- A refusal cannot leave half of a decision in the record.
- Escalation to an inspector does not release the normative debtor.
- A sensor reading is bound to a registered instrument profile.
- `STOP` remains a local action, not proof of `h1`.

A logical rollback does not restore drilled concrete. The physical outcome and the obligation therefore remain even if the explanation later changes.

# 12. Interdisciplinary bridges

## Explicit bridge: event semantics and belief revision

The event layer determines what happened and within which causal prefix. The epistemic layer determines how that event changed belief. Conflating the layers turns a change in the world into “a new opinion,” or turns an opinion into an event.

## Hidden bridge 1: quantum instrument and witness

In both cases an outcome is incomplete without the procedure, context, and subsequent state update. The result is not a free-floating answer.

## Hidden bridge 2: anatomical regulation

The continuity of an organism is not localised in one cell. It is maintained through distributed feedback, repair, and resource loops. This is an engineering analogy, not an argument for machine life.

## Hidden bridge 3: normative identity and distributed transaction

An obligation is transferred through atomic lineage, not textual resemblance. The same structural requirement appears in a financial transfer: the old state must not disappear before an accepted new holder exists.

# 13. Falsification

The candidate is rejected if:

- an out-of-order cut creates durable authorisation;
- a failed cut leaves a mutation;
- a dirty obligation enters through creation;
- escalation releases the normative debtor;
- an evidence ID changes content;
- SOC returns an unevaluated action;
- a rejected request ID is rebound to a new digest;
- a physical effect occurs without durable authorisation;
- an assignment or plan changes content under the same identity;
- the analysis implementations disagree on a frozen valid contract;
- an unrelated setup failure is counted as a mutation kill;
- an audit proposal is presented as proof of semantic reconciliation.

The normative Python surfaces include regression and property tests plus sixteen target-specific source mutants. The Windows runner has a separate disposable positive and negative control. Independent Windows Phase 1 completed with `PASS`.

# 14. Limitations

- bounded model and test space;
- no proof assistant or unbounded model checking;
- reference monitors are not production controllers;
- the sixth blind model review is not human peer review;
- no external human conceptual review has been completed;
- no external-rater pilot has been completed;
- no registered protocol has been submitted;
- no main matched-control study has been run;
- no real quantum or photonic adapter experiment has been run;
- no empirical continuity or identity result exists;
- privacy, retention, and erasure semantics for a full temporal witness remain open.

# 15. Conclusion

`C` is not defined by a qubit, parameter count, or the literary continuity of a profile. A working candidate is defined more strictly: by the ability to preserve causal provenance, make a local commitment without globally closing the model, carry obligations, verify authority before physical effect, and accept equivalence with a strong control when no measurable difference remains.

A binary answer closes one question. Centering is tested by how the system preserves everything that answer did not close.

# References

1. Alchourrón, C. E., Gärdenfors, P., & Makinson, D. (1985). On the logic of theory change. *Journal of Symbolic Logic*, 50(2), 510-530.
2. Darwiche, A., & Pearl, J. (1997). On the logic of iterated belief revision. *Artificial Intelligence*, 89, 1-29.
3. Doyle, J. (1979). A truth maintenance system. *Artificial Intelligence*, 12(3), 231-272.
4. Lamport, L. (1978). Time, clocks, and the ordering of events in a distributed system. *Communications of the ACM*, 21(7), 558-565.
5. Park, J. S., et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. *UIST 2023*.
6. Wootters, W. K., & Zurek, W. H. (1982). A single quantum cannot be cloned. *Nature*, 299, 802-803.
7. Zurek, W. H. (2003). Decoherence, einselection, and the quantum origins of the classical. *Reviews of Modern Physics*, 75, 715-775.

# Appendix A. Public open-review status

The exact reviewed `v0.8.1` surface includes:

```text
Windows Phase 1:                 PASS
v0.8 tests:                      190/190
legacy v0.7 tests:               177/177
thread/process contention:       100/20
source mutants:                  16/16 killed
cross-analysis fixtures:         6/6
full-test negative control:      PASS
sixth blind conceptual review:   NO_CANDIDATE_BLOCKERS_FOUND
```

This result is not human peer review. The public release opens two external tracks:

1. independent human conceptual review;
2. an endpoint-rater pilot for `SRR`, `OCA`, `PAR`, and `RCS`.

Materials for both tracks are included in the public package and on the project page. Any newly confirmed blocker requires a new version; no hidden ontological residual is permitted after observed equivalence.
