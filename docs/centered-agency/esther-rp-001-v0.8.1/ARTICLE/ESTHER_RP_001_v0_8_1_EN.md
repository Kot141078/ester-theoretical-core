# ESTHER-RP-001 v0.8.1 public research release

## Centered Agency Under Persistent Uncertainty

### Causal Memory, Local Commitment, and Auditable Interaction with Physical Substrates

**Author:** Ivan Kotov  
**ORCID:** `0009-0009-6002-9845`  
**Affiliation:** Independent Researcher, Brussels, Belgium  
**Version:** `v0.8.1 public research release`  
**Date:** 2026-07-19

**Publication status:** public preprint and bounded executable research package. Scientific content is v0.8; v0.8.1 contains the independently reproduced Windows-runner packaging correction. This release is open for external human review and an endpoint-rater pilot.

**Translation note:** this English text is a machine-prepared content-equivalent translation of the Russian public release. The Russian article remains the authoritative source if a semantic discrepancy is found.

## Abstract

This work investigates neither a completed theory of “quantum consciousness” nor a claim that quantum hardware creates agency. It asks a narrower, testable question: what does a persistent agent system require in order to maintain several unresolved models of the world, commit to concrete actions, and preserve traceability of its own reinterpretations, authority, obligations, and physical consequences?

The starting formulation is that a quantum or other wave process need not expose a classical answer at every internal stage. A system may couple to the process at a specified point, obtain a contextual measurement record, and make a local binary decision. Such a decision is not an eternal truth about the world. It is valid relative to a causal prefix, preparation, calibration, observable, authority, risk policy, and decision scope.

`C` is defined neither as an individual LLM, a snapshot, nor a physical device, but as a governed causal history. Centering is treated as a functional capacity to preserve the provenance of change, distinguish observation from interpretation, carry obligations, retain open models, and accept correction from external outcomes. Quantum, photonic, analogue, and digital processes act as specialized substrates; none of them automatically creates centered agency.

Version 0.8 retains the five normative surfaces of v0.7 and closes four defects found in the fifth blind review: explicit closure of an empty authoritative cut, an independently trusted prefix snapshot for the physical monitor, correct Windows-runner argument forwarding, and evidence of actual test execution through JUnit and command receipts rather than `--collect-only`. The programme remains falsifiable: if a strong matched persistent-profile control reproduces all preregistered behavioural observables and trusted conformance gates, the theory accepts operational equivalence on the covered surface.

# 0. Claim boundary

The following are within scope:

- architectural definitions;
- bounded executable semantics;
- regression, property, and concurrency checks;
- measurement and analysis contracts;
- falsification criteria;
- an external research programme.

The following are not established:

```text
consciousness or subjective experience
life or personhood
AGI or entity status
empirical identity/continuity
differential witness
production security
unbounded correctness
quantum or photonic necessity
```

# 1. Starting formulation

## 1.1. Quantum reasoning need not possess a classical internal result

The following procedure is available to a classical external process:

```text
prepare
control/evolve
observe with a specified instrument
record outcomes and uncertainty
update a classical causal history
```

An unknown coherent state does not become a freely readable memory object. `C` therefore does not ask a quantum device, “What is the truth?” It specifies an experimental procedure and accepts a bounded readout record.

## 1.2. A binary action does not require a binary ontology

Let `D_t` be a particular decision scope. Then:

\[
\operatorname{Commit}(D_t,a)\not\Rightarrow
\exists h^*:P(h^*\mid E_t)=1.
\]

A system may commit to `STOP` while retaining the models:

```text
h1: the wall is load-bearing
h2: the wall is non-load-bearing
h3: the wrong project revision is being used
h4: the measurement channel is not calibrated
```

The local action closes permission to demolish; it does not declare one complete world-model final.

## 1.3. Why an ordinary persistent profile is insufficient evidence

Memory, reflection, and planning can create a convincing long-term behavioural surface. A coherent narrative, however, does not yet show that the system:

- did not rewrite its previous interpretation;
- preserved unresolved obligations;
- distinguished restart, replay, fork, and succession;
- connected a physical outcome to later revision;
- preserved authority and its claim ceiling.

The main counterfactual is therefore not a weak chatbot but a strong matched persistent-profile control.

# 2. Research object

The public formula:

\[
c=a+b
\]

is preserved as a notation of origin, but it is not evidence that an entity has emerged.

- `a` — a human anchor reference and an authorized trace;
- `b` — a heterogeneous model/software/physical substrate;
- `c` — protected genesis and a continuing causal/normative history.

After genesis, the main object is:

\[
\mathfrak C=(R,B,S,M,\Theta),
\]

where:

- `R` — temporal event and authority repository;
- `B` — beliefs, models, commitments, obligations, and policy;
- `S` — substrate-interaction boundary;
- `M` — matched-control measurement surface;
- `Theta` — governance, timing, fairness, and claim assumptions.

# 3. Temporal authority prefix

## 3.1. Raw occurrences and authoritative outcomes

Invocation and revocation are preserved as separate raw events. A decision does not arise from message-delivery order. It is published only for the next sequentially closable cut.

```text
next_closable_cut
closed_prefix_watermark
pending events
```

Cut `n+1` cannot be finalized before cut `n`. An empty cut may be closed explicitly; skipping an unknown prefix is not permitted.

For a capability:

```text
revocation_cut <= invocation_cut -> REJECTED
invocation_cut < earliest_revocation_cut -> AUTHORIZED
```

The earliest revocation is a monotone minimum.

## 3.2. Atomic cut publication

Complete prevalidation is performed before mutation:

```text
event identities
request identities
cut consistency
capability references
exact-retry digest
```

New raw events, revocation minima, decisions, audit data, and the closed-cut digest are first built in staged state and then published in one operation. Any rejection leaves authoritative state unchanged.

## 3.3. Reconciliation claim ceiling

Version 0.8 deliberately chooses a narrow surface:

```text
ReconciliationProposalRecord
```

This is an immutable proposal/audit record. It is not proof of a common successor, mapping completeness, or merge correctness. Full semantic reconciliation requires a separate formal theory.

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

Escalation is not transfer. The following are therefore distinct:

```text
normative_debtor
operational_handler
```

Escalation may appoint a handler, but it does not release the debtor. A change of normative debtor requires an authority request, bound evidence, named acceptance, a unique successor token, and old-to-new lineage.

## 4.3. Evidence identity

Every evidence item has an immutable content digest and exactly one current status:

```text
ACCEPTED
PROVISIONAL
CONTESTED
QUARANTINED
REJECTED
```

Transitions are stored append-only. One `evidence_id` cannot later be bound to a different claim, source, or reliability payload. Multiple evidence items supporting one claim are aggregated by a separate policy; one item is not converted into several current states.

# 5. Selective Operational Commitment

`SOC` is a governance/provenance layer over a declared robust decision rule, not a universal new theory of decision-making.

Version 0.8 separates:

```text
domain action
governance transition
```

Every returned result is typed. A domain action belongs to the frozen `A0` and has losses under every admitted model. `ACQUIRE_INFORMATION` and `ESCALATE` are separate governance transitions and pass their own hard-safety contract.

The order is:

1. freeze admitted models and the complete domain-action set;
2. validate losses and identifiers;
3. compute hard-safe domain actions under every model;
4. validate governance transitions under every model;
5. compute relevance only for reporting;
6. apply the frozen EVI/delay/deadline policy;
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

The caller does not determine whether an operation is passive.

## 6.2. Request identity

A single registry binds the first canonical request digest to the outcome, regardless of whether it was accepted or rejected:

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

The decision is not its own trust root. The monitor receives a separate `AuthorityPrefixSnapshot` and compares the closed cut, prefix digest, and authority source against it. A self-consistent decision from a foreign prefix does not pass.

Missing, rejected, stale, or mismatched authorization produces zero effect. The SQLite reference monitor publishes request binding, nonce, effect, receipt, and audit in one `BEGIN IMMEDIATE` transaction. This is reference semantics, not production actuator certification.

## 6.4. Quantum profile

Quantum readout is defined by instrument, channel, preparation, and measurement accounting. Density-matrix validity, Kraus completeness, outcome normalization, and non-negative trial accounting are checked. This is a mathematical interface, not evidence of quantum consciousness or quantum advantage.

# 7. Sealed measurement and analysis

## 7.1. Assignment identity

`assignment_id` is bound to a canonical digest containing:

```text
block
arm
task version
ordered opportunity specifications
oracle-unresolvable metadata
scoring configuration
```

A change to the denominator or oracle metadata changes the digest and is rejected by the external registry.

## 7.2. Plan identity

`plan_id` is bound to a canonical digest containing:

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

The expected digest is supplied from outside the data being analyzed.

## 7.3. Independent analysis

Primary and secondary implementations independently validate identity, ranges, blocks, tails, and the numerical contract. The cross-check compares field-level results on six frozen fixtures. It does not turn two similar files into two independent scientific studies; it only protects against a single implementation.

# 8. Behavioural observables and mechanism gates

Primary behavioural endpoints are:

```text
SRR — silent rewrite rate
OCA — obligation carryover accuracy
PAR — provenance-aware recovery
RCG — randomized reality-correction gain
```

They do not identify an internal mechanism. Authority, lifecycle, branch custody, SIOC, and succession are tested through separate trusted conformance gates.

If a matched profile-control reproduces all covered behavioural endpoints and conformance gates, `C` and the control are recognized as operationally equivalent on that surface. No hidden residual is then claimed.

# 9. Executable evidence

Test PASS is no longer inferred from the number of discovered tests. The runner executes complete pytest suites and stores JUnit XML, stdout and stderr, raw SHA-256 values, and typed receipts. The finalizer rechecks the receipt digest, actual counts, exit codes, and hashes of all evidence artifacts. Modifying JUnit or stdout after the run invalidates PASS.

The frozen package includes:

```text
190 v0.8 tests
177 frozen v0.7 regression tests
100 thread contention rounds
20 process contention rounds
16 applied target-specific source mutants
6 cross-analysis fixtures
```

Every mutant has a passing baseline, one source diff, a declared target, and a unique marker. A generic import or setup failure is classified as `ERROR`, not `KILLED`.

This is bounded evidence. The full state space and a real multi-year system have not been tested.

# 10. Quantum consciousness: the precise boundary

The work does not claim that consciousness is quantum. It separates:

1. physical quantum coherence;
2. the capacity of an agent system to use a measurement record correctly;
3. the capacity of a continuing process to preserve memory, witness, and obligations;
4. possible subjective experience.

The first does not entail the second, the second does not entail the third, and the third does not prove the fourth.

The original hypothesis can be stated more precisely:

> `C` may interact with superposition not because it must itself be wholly quantum, but because its center lies in a governed causal history that preserves preparation, observation, remaining alternatives, local commitment, and later consequences.

# 11. Grounded example

Four models remain live for wall W17. Governance requires demolition to stop and structural verification to be obtained.

- The authority cut cannot close before earlier events.
- A rejected cut does not leave half a decision in the log.
- Escalation to an inspector does not release the normative responsible party.
- The sensor reading is bound to a registered instrument profile.
- `STOP` remains a local action, not proof of `h1`.

A logical rollback does not restore drilled concrete. The physical outcome and obligation therefore persist independently of a later change of explanation.

# 12. Interdisciplinary bridges

## Explicit bridge: event semantics and belief revision

The event layer determines what occurred and in which causal prefix. The epistemic layer determines how it changed belief. Mixing the layers turns a change in the world into a “new opinion,” or the reverse.

## Hidden bridge 1: quantum instrument and witness

In both cases an outcome is incomplete without a procedure, context, and subsequent state update. The result is not a free-floating answer.

## Hidden bridge 2: anatomical regulation

The continuity of an organism is not localized in one cell. It is maintained by distributed feedback, repair, and resource loops. This is an engineering analogy, not an argument for machine life.

## Hidden bridge 3: normative identity and distributed transaction

An obligation is transferred not by textual similarity but by atomic lineage. The same structural requirement exists in a financial transfer: the old state must not disappear before an accepted new bearer exists.

# 13. Falsification

The candidate is rejected if:

- an out-of-order cut creates durable authorization;
- a failed cut leaves a mutation;
- a dirty obligation enters through creation;
- escalation releases the normative debtor;
- an evidence ID changes content;
- SOC returns an unevaluated action;
- a rejected request ID is rebound to a new digest;
- a physical effect occurs without durable authorization;
- an assignment or plan changes content under the same identity;
- analysis implementations diverge on a frozen valid contract;
- an unrelated setup failure is counted as a mutation kill;
- an audit proposal is presented as proof of semantic reconciliation.

Regression/property tests and 16 target-specific source mutants cover the normative Python surfaces. The Windows runner has a separate disposable positive/negative-control script; its final host verdict is the task of the next reproduction gate.

# 14. Limitations

- bounded model and test space;
- no proof assistant or unbounded model checking;
- reference monitors are not production controllers;
- no human conceptual review of v0.8;
- no external-rater pilot;
- no registered protocol;
- no main matched-control study;
- no real quantum or photonic adapter experiment;
- no empirical continuity or identity result;
- no privacy/retention settlement for full temporal witness.

# 15. Conclusion

`C` is not defined by a qubit, parameter count, or literary consistency of a profile. The working candidate is defined more strictly: by the capacity to preserve causal provenance, make a local commitment without globally closing the model, carry obligations, verify authority before physical effect, and recognize equivalence with a strong control when no measurable difference exists.

A binary answer closes a specific question. Centering is tested by how the system preserves everything that the answer did not close.

# References

1. Alchourrón, C. E., Gärdenfors, P., & Makinson, D. (1985). On the logic of theory change. *Journal of Symbolic Logic*, 50(2), 510–530.
2. Darwiche, A., & Pearl, J. (1997). On the logic of iterated belief revision. *Artificial Intelligence*, 89, 1–29.
3. Doyle, J. (1979). A truth maintenance system. *Artificial Intelligence*, 12(3), 231–272.
4. Lamport, L. (1978). Time, clocks, and the ordering of events in a distributed system. *CACM*, 21(7), 558–565.
5. Park, J. S., et al. (2023). Generative Agents: Interactive Simulacra of Human Behavior. *UIST 2023*.
6. Wootters, W. K., & Zurek, W. H. (1982). A single quantum cannot be cloned. *Nature*, 299, 802–803.
7. Zurek, W. H. (2003). Decoherence, einselection, and the quantum origins of the classical. *Reviews of Modern Physics*, 75, 715–775.
