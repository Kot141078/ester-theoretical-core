from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass, replace
from enum import Enum
from threading import RLock
from typing import Iterable, Mapping, Sequence

from common_v07 import (
    ObligationStatus,
    TERMINAL_OBLIGATION_STATUSES,
    require_nonempty_text,
    require_nonnegative_int,
    sha256_digest,
)


# ---------------------------------------------------------------------------
# Typed dependency surface
# ---------------------------------------------------------------------------


class DependencyKind(str, Enum):
    PHYSICAL_CAUSE = "PHYSICAL_CAUSE"
    INFORMATIONAL = "INFORMATIONAL"
    RECORD_ORDER = "RECORD_ORDER"
    CONTESTED = "CONTESTED"


@dataclass(frozen=True)
class TimeInterval:
    start: int | None
    end: int | None

    @property
    def known(self) -> bool:
        return self.start is not None and self.end is not None


@dataclass(frozen=True)
class DependencyEdge:
    source_id: str
    target_id: str
    kind: DependencyKind
    source_occurrence: TimeInterval
    target_occurrence: TimeInterval
    reason: str = ""


def validate_dependency(edge: DependencyEdge) -> bool:
    if edge.source_id == edge.target_id:
        return False
    if edge.kind is DependencyKind.PHYSICAL_CAUSE:
        if not edge.source_occurrence.known or not edge.target_occurrence.known:
            return False
        assert edge.source_occurrence.end is not None
        assert edge.target_occurrence.start is not None
        return edge.source_occurrence.end <= edge.target_occurrence.start
    return True


# ---------------------------------------------------------------------------
# v0.7 authority prefix and atomic cut semantics
# ---------------------------------------------------------------------------


class AuthorityEventKind(str, Enum):
    INVOCATION = "INVOCATION"
    REVOCATION = "REVOCATION"


@dataclass(frozen=True)
class AuthorityEvent:
    event_id: str
    kind: AuthorityEventKind
    capability_id: str
    capability_version: int
    cut: int
    request_id: str | None = None
    request_digest: str | None = None
    effect_id: str | None = None

    def validate(self) -> None:
        require_nonempty_text(self.event_id, "event_id")
        require_nonempty_text(self.capability_id, "capability_id")
        require_nonnegative_int(self.capability_version, "capability_version")
        require_nonnegative_int(self.cut, "cut")
        if self.kind is AuthorityEventKind.INVOCATION:
            require_nonempty_text(self.request_id or "", "request_id")
            require_nonempty_text(self.request_digest or "", "request_digest")
            require_nonempty_text(self.effect_id or "", "effect_id")
        else:
            if self.request_id is not None or self.request_digest is not None or self.effect_id is not None:
                raise ValueError("revocation events cannot carry request/effect fields")


@dataclass(frozen=True)
class AuthorityDecision:
    decision_id: str
    request_id: str
    request_digest: str
    capability_id: str
    capability_version: int
    invocation_cut: int
    closed_prefix_digest: str
    earliest_revocation_cut: int | None
    status: str
    effect_id: str | None
    reason: str | None
    raw_event_ids: tuple[str, ...]
    decision_digest: str

    def verify_digest(self) -> bool:
        payload = {
            "decision_id": self.decision_id,
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "capability_id": self.capability_id,
            "capability_version": self.capability_version,
            "invocation_cut": self.invocation_cut,
            "closed_prefix_digest": self.closed_prefix_digest,
            "earliest_revocation_cut": self.earliest_revocation_cut,
            "status": self.status,
            "effect_id": self.effect_id,
            "reason": self.reason,
            "raw_event_ids": self.raw_event_ids,
        }
        return self.decision_digest == sha256_digest(payload)


class AuthorityCutLedger:
    """A prefix-closed, staged authority ledger.

    The first admissible cut is fixed at construction. A cut can only be closed
    when it is exactly the next cut in the authoritative prefix. Every batch is
    fully validated and resolved against staged copies before any state becomes
    visible. An exception therefore leaves every authoritative projection
    unchanged.
    """

    def __init__(self, *, start_cut: int = 0) -> None:
        require_nonnegative_int(start_cut, "start_cut")
        self._lock = RLock()
        self._start_cut = start_cut
        self._next_cut = start_cut
        self._closed_cuts: dict[int, str] = {}
        self._closed_prefix_digest = sha256_digest(("authority-prefix", start_cut))
        self._raw_events: dict[str, AuthorityEvent] = {}
        self._earliest_revocation_cut: dict[tuple[str, int], int] = {}
        self._decisions: dict[str, AuthorityDecision] = {}
        self._decisions_by_cut: dict[int, tuple[str, ...]] = {}
        self._audit: tuple[str, ...] = ()

    @property
    def start_cut(self) -> int:
        return self._start_cut

    @property
    def next_cut(self) -> int:
        with self._lock:
            return self._next_cut

    @property
    def closed_prefix_watermark(self) -> int | None:
        with self._lock:
            return None if not self._closed_cuts else self._next_cut - 1

    @property
    def closed_prefix_digest(self) -> str:
        with self._lock:
            return self._closed_prefix_digest

    @property
    def raw_events(self) -> tuple[AuthorityEvent, ...]:
        with self._lock:
            return tuple(self._raw_events[k] for k in sorted(self._raw_events))

    @property
    def decisions(self) -> tuple[AuthorityDecision, ...]:
        with self._lock:
            return tuple(self._decisions[k] for k in sorted(self._decisions))

    @property
    def audit(self) -> tuple[str, ...]:
        with self._lock:
            return self._audit

    def earliest_revocation_cut(self, capability_id: str, capability_version: int = 1) -> int | None:
        with self._lock:
            return self._earliest_revocation_cut.get((capability_id, capability_version))

    def decision_for(self, request_id: str) -> AuthorityDecision:
        with self._lock:
            return self._decisions[request_id]

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "start_cut": self._start_cut,
                "next_cut": self._next_cut,
                "closed_cuts": dict(self._closed_cuts),
                "closed_prefix_digest": self._closed_prefix_digest,
                "raw_events": {k: asdict(v) for k, v in sorted(self._raw_events.items())},
                "earliest_revocation_cut": {
                    f"{cap}:{ver}": cut
                    for (cap, ver), cut in sorted(self._earliest_revocation_cut.items())
                },
                "decisions": {k: asdict(v) for k, v in sorted(self._decisions.items())},
                "decisions_by_cut": {str(k): list(v) for k, v in sorted(self._decisions_by_cut.items())},
                "audit": list(self._audit),
            }

    @staticmethod
    def _batch_digest(cut: int, events: Sequence[AuthorityEvent]) -> str:
        return sha256_digest(
            {
                "cut": cut,
                "events": sorted(
                    (
                        e.event_id,
                        e.kind.value,
                        e.capability_id,
                        e.capability_version,
                        e.request_id,
                        e.request_digest,
                        e.effect_id,
                    )
                    for e in events
                ),
            }
        )

    def commit_cut(self, cut: int, events: Sequence[AuthorityEvent]) -> tuple[AuthorityDecision, ...]:
        require_nonnegative_int(cut, "cut")
        if not events:
            raise ValueError("a cut commit must declare its complete event batch")
        for event in events:
            event.validate()
            if event.cut != cut:
                raise ValueError("all events must belong to the committed cut")

        event_ids = [e.event_id for e in events]
        request_ids = [e.request_id for e in events if e.kind is AuthorityEventKind.INVOCATION]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("duplicate event id in cut batch")
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("duplicate request id in cut batch")
        batch_digest = self._batch_digest(cut, events)

        with self._lock:
            prior_digest = self._closed_cuts.get(cut)
            if prior_digest is not None:
                if prior_digest != batch_digest:
                    raise ValueError("cut already closed with a different batch")
                return tuple(self._decisions[rid] for rid in self._decisions_by_cut.get(cut, ()))

            # Prefix completeness is a hard precondition. No mutation has happened.
            if cut != self._next_cut:
                raise ValueError(f"out-of-order cut: expected {self._next_cut}, received {cut}")
            if any(e.event_id in self._raw_events for e in events):
                raise ValueError("event id already used in another cut")
            if any(rid in self._decisions for rid in request_ids if rid is not None):
                raise ValueError("request id already decided in an earlier cut")

            # Stage all projections. They are published only after every operation succeeds.
            staged_raw = dict(self._raw_events)
            staged_revocations = dict(self._earliest_revocation_cut)
            staged_decisions = dict(self._decisions)
            staged_audit = list(self._audit)

            for event in sorted(events, key=lambda e: (e.kind.value, e.event_id)):
                staged_raw[event.event_id] = event
                staged_audit.append(f"RawAuthorityEvent:{event.event_id}:{event.kind.value}@{cut}")
                if event.kind is AuthorityEventKind.REVOCATION:
                    key = (event.capability_id, event.capability_version)
                    previous = staged_revocations.get(key)
                    staged_revocations[key] = cut if previous is None else min(previous, cut)

            staged_prefix_digest = sha256_digest(
                {
                    "previous_prefix_digest": self._closed_prefix_digest,
                    "cut": cut,
                    "batch_digest": batch_digest,
                }
            )
            raw_ids = tuple(sorted(event_ids))
            decisions: list[AuthorityDecision] = []
            for event in sorted(
                (e for e in events if e.kind is AuthorityEventKind.INVOCATION),
                key=lambda e: e.request_id or "",
            ):
                assert event.request_id is not None
                assert event.request_digest is not None
                assert event.effect_id is not None
                key = (event.capability_id, event.capability_version)
                revocation_cut = staged_revocations.get(key)
                authorized = revocation_cut is None or event.cut < revocation_cut
                payload = {
                    "decision_id": f"decision:{event.request_id}",
                    "request_id": event.request_id,
                    "request_digest": event.request_digest,
                    "capability_id": event.capability_id,
                    "capability_version": event.capability_version,
                    "invocation_cut": event.cut,
                    "closed_prefix_digest": staged_prefix_digest,
                    "earliest_revocation_cut": revocation_cut,
                    "status": "AUTHORIZED" if authorized else "REJECTED",
                    "effect_id": event.effect_id if authorized else None,
                    "reason": None if authorized else "REVOKED_AT_OR_BEFORE_INVOCATION_CUT",
                    "raw_event_ids": raw_ids,
                }
                decision = AuthorityDecision(**payload, decision_digest=sha256_digest(payload))
                staged_decisions[event.request_id] = decision
                staged_audit.append(f"AuthorityDecision:{event.request_id}:{decision.status}")
                decisions.append(decision)

            # One publish point.
            self._raw_events = staged_raw
            self._earliest_revocation_cut = staged_revocations
            self._decisions = staged_decisions
            self._audit = tuple(staged_audit)
            self._closed_cuts[cut] = batch_digest
            self._closed_prefix_digest = staged_prefix_digest
            self._decisions_by_cut[cut] = tuple(d.request_id for d in decisions)
            self._next_cut += 1
            return tuple(decisions)


# ---------------------------------------------------------------------------
# Reconciliation proposal surface
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BranchConfiguration:
    configuration_id: str
    events: frozenset[str]

    def validate(self) -> None:
        require_nonempty_text(self.configuration_id, "configuration_id")
        if not self.events:
            raise ValueError("branch configuration requires at least one event")
        if any(not isinstance(e, str) or not e.strip() for e in self.events):
            raise ValueError("branch event IDs must be non-empty strings")


@dataclass(frozen=True)
class ReconciliationProposalRecord:
    record_id: str
    source_configuration_ids: tuple[str, str]
    proposed_successor_id: str
    mapping: tuple[tuple[str, str], ...]
    unresolved_residues: tuple[str, ...]
    record_digest: str
    semantic_validity_claim: bool = False


class BranchRepository:
    """Stores configurations and opaque reconciliation proposals.

    A proposal is an auditable statement. It is not proof that the proposed
    successor exists or that a mapping is semantically complete. Full merge
    semantics are deliberately outside the v0.7 claim surface.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._configurations: dict[str, BranchConfiguration] = {}
        self._proposals: dict[str, ReconciliationProposalRecord] = {}

    @property
    def configurations(self) -> Mapping[str, BranchConfiguration]:
        with self._lock:
            return dict(self._configurations)

    @property
    def reconciliation_proposals(self) -> Mapping[str, ReconciliationProposalRecord]:
        with self._lock:
            return dict(self._proposals)

    def add_configuration(self, config: BranchConfiguration) -> None:
        config.validate()
        with self._lock:
            if config.configuration_id in self._configurations:
                raise ValueError("duplicate configuration")
            self._configurations[config.configuration_id] = config

    def record_reconciliation_proposal(
        self,
        *,
        record_id: str,
        left_id: str,
        right_id: str,
        proposed_successor_id: str,
        mapping: Iterable[tuple[str, str]] = (),
        unresolved_residues: Iterable[str] = (),
    ) -> tuple[ReconciliationProposalRecord, bool]:
        require_nonempty_text(record_id, "record_id")
        require_nonempty_text(proposed_successor_id, "proposed_successor_id")
        if left_id == right_id:
            raise ValueError("proposal requires two distinct source configurations")
        with self._lock:
            if left_id not in self._configurations or right_id not in self._configurations:
                raise KeyError("both source configurations must exist")
            payload = {
                "record_id": record_id,
                "sources": tuple(sorted((left_id, right_id))),
                "proposed_successor_id": proposed_successor_id,
                "mapping": tuple(sorted(tuple(pair) for pair in mapping)),
                "unresolved_residues": tuple(sorted(str(x) for x in unresolved_residues)),
                "semantic_validity_claim": False,
            }
            digest = sha256_digest(payload)
            prior = self._proposals.get(record_id)
            if prior is not None:
                if prior.record_digest != digest:
                    raise ValueError("proposal record ID already bound to different content")
                return prior, False
            record = ReconciliationProposalRecord(
                record_id=record_id,
                source_configuration_ids=payload["sources"],
                proposed_successor_id=proposed_successor_id,
                mapping=payload["mapping"],
                unresolved_residues=payload["unresolved_residues"],
                record_digest=digest,
                semantic_validity_claim=False,
            )
            self._proposals[record_id] = record
            return record, True


# ---------------------------------------------------------------------------
# Product refinement: physical stutter + immutable audit receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RejectionReceipt:
    request_id: str
    request_digest: str
    reason: str
    receipt_digest: str


class ProductRefinementLedger:
    def __init__(self) -> None:
        self._lock = RLock()
        self._rejections: dict[str, RejectionReceipt] = {}
        self._audit: tuple[str, ...] = ()
        self._physical_effects: tuple[str, ...] = ()

    @property
    def audit_events(self) -> tuple[str, ...]:
        with self._lock:
            return self._audit

    @property
    def physical_effects(self) -> tuple[str, ...]:
        with self._lock:
            return self._physical_effects

    def reject(self, *, request_id: str, request_digest: str, reason: str) -> RejectionReceipt:
        require_nonempty_text(request_id, "request_id")
        require_nonempty_text(request_digest, "request_digest")
        require_nonempty_text(reason, "reason")
        with self._lock:
            prior = self._rejections.get(request_id)
            if prior is not None:
                if prior.request_digest != request_digest:
                    raise ValueError("request id already bound to a different digest")
                return prior
            receipt = RejectionReceipt(
                request_id=request_id,
                request_digest=request_digest,
                reason=reason,
                receipt_digest=sha256_digest((request_id, request_digest, reason)),
            )
            self._rejections[request_id] = receipt
            self._audit += (f"RejectionRecorded:{receipt.receipt_digest}",)
            return receipt


# ---------------------------------------------------------------------------
# Bounded liveness profile retained from v0.6
# ---------------------------------------------------------------------------


class BranchStatus(str, Enum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    CLOSED = "CLOSED"
    HANDOFF_ACCEPTED = "HANDOFF_ACCEPTED"


GLOBAL_RESPONSE_BOUND = 8
LOCAL_REVIEW_WINDOW = 2
MAX_DEFERS = 2


@dataclass(frozen=True)
class BranchWorkflowState:
    global_remaining: int = GLOBAL_RESPONSE_BOUND
    local_remaining: int = LOCAL_REVIEW_WINDOW
    defer_budget: int = MAX_DEFERS
    status: BranchStatus = BranchStatus.OPEN
    escalation_requested: bool = False

    @property
    def terminal(self) -> bool:
        return self.status is not BranchStatus.OPEN


def branch_successors(state: BranchWorkflowState, *, mutant: str | None = None) -> tuple[tuple[str, BranchWorkflowState], ...]:
    if state.terminal:
        return ()
    out: list[tuple[str, BranchWorkflowState]] = []
    if state.local_remaining > 0 and state.global_remaining > 0:
        out.append(("Tick", replace(state, global_remaining=state.global_remaining - 1, local_remaining=state.local_remaining - 1)))
    out.append(("Review", replace(state, status=BranchStatus.REVIEWED)))
    out.append(("Close", replace(state, status=BranchStatus.CLOSED)))
    if not state.escalation_requested:
        out.append(("RequestEscalation", replace(state, escalation_requested=True)))
    else:
        out.append(("AcceptHandoff", replace(state, status=BranchStatus.HANDOFF_ACCEPTED)))
    if state.local_remaining == 0 and state.defer_budget > 0:
        if mutant == "infinite_defer":
            out.append(("Defer", replace(state, global_remaining=GLOBAL_RESPONSE_BOUND, local_remaining=LOCAL_REVIEW_WINDOW, defer_budget=MAX_DEFERS)))
        else:
            out.append(("Defer", replace(state, local_remaining=min(LOCAL_REVIEW_WINDOW, state.global_remaining), defer_budget=state.defer_budget - 1)))
    return tuple(out)


def explore_branch_workflow(*, mutant: str | None = None) -> dict:
    start = BranchWorkflowState()
    queue = deque([start])
    seen = {start}
    edges: dict[BranchWorkflowState, list[tuple[str, BranchWorkflowState]]] = defaultdict(list)
    while queue:
        state = queue.popleft()
        for action, nxt in branch_successors(state, mutant=mutant):
            edges[state].append((action, nxt))
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

    nonterminal = {s for s in seen if not s.terminal}
    color: dict[BranchWorkflowState, int] = {}
    cycle_trace: list[str] = []

    def dfs_cycle(node: BranchWorkflowState, path: list[str]) -> bool:
        color[node] = 1
        for action, nxt in edges.get(node, []):
            if nxt.terminal:
                continue
            if color.get(nxt, 0) == 0:
                if dfs_cycle(nxt, path + [action]):
                    return True
            elif color.get(nxt) == 1:
                cycle_trace.extend(path + [action])
                return True
        color[node] = 2
        return False

    has_cycle = any(color.get(s, 0) == 0 and dfs_cycle(s, []) for s in nonterminal)
    dead_ends = [s for s in nonterminal if not edges.get(s)]
    observed_worst_case: int | None = None
    if not has_cycle:
        memo: dict[BranchWorkflowState, int] = {}

        def longest_ticks(node: BranchWorkflowState) -> int:
            if node.terminal:
                return 0
            if node in memo:
                return memo[node]
            candidates = [(1 if action == "Tick" else 0) + longest_ticks(nxt) for action, nxt in edges.get(node, [])]
            memo[node] = max(candidates, default=0)
            return memo[node]

        observed_worst_case = longest_ticks(start)

    return {
        "reachable_states": len(seen),
        "transition_count": sum(len(v) for v in edges.values()),
        "nonterminal_cycle": has_cycle,
        "cycle_trace": cycle_trace[:20],
        "nonterminal_dead_ends": [repr(s) for s in dead_ends],
        "declared_ceiling_ticks": GLOBAL_RESPONSE_BOUND,
        "observed_worst_case_ticks": observed_worst_case,
        "pass": not has_cycle and not dead_ends and observed_worst_case is not None and observed_worst_case <= GLOBAL_RESPONSE_BOUND,
    }


# ---------------------------------------------------------------------------
# Authority-guarded obligation repository
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceReceipt:
    receipt_id: str
    actor: str
    authority_source: str
    action: str
    obligation_id: str
    reason: str
    evidence_refs: tuple[str, ...]
    provenance_digest: str

    def validate_for(self, *, token: "ObligationToken", action: str, actor: str) -> None:
        require_nonempty_text(self.receipt_id, "receipt_id")
        if self.actor != actor:
            raise PermissionError("evidence receipt actor mismatch")
        if self.authority_source != token.authority_id:
            raise PermissionError("evidence authority source mismatch")
        if self.action != action or self.obligation_id != token.obligation_id:
            raise ValueError("evidence receipt is not bound to this transition")
        require_nonempty_text(self.reason, "evidence reason")
        require_nonempty_text(self.provenance_digest, "evidence provenance_digest")
        if not self.evidence_refs or any(not str(x).strip() for x in self.evidence_refs):
            raise ValueError("evidence receipt requires non-empty evidence references")


@dataclass(frozen=True)
class HandoffAcceptanceReceipt:
    receipt_id: str
    request_id: str
    obligation_id: str
    actor: str
    transferee: str
    provenance_digest: str

    def validate(self, *, request_id: str, obligation_id: str, transferee: str) -> None:
        require_nonempty_text(self.receipt_id, "receipt_id")
        if self.request_id != request_id or self.obligation_id != obligation_id:
            raise ValueError("handoff receipt request/token mismatch")
        if self.actor != transferee or self.transferee != transferee:
            raise PermissionError("named transferee must personally accept the handoff")
        require_nonempty_text(self.provenance_digest, "handoff provenance_digest")


@dataclass(frozen=True)
class ObligationToken:
    obligation_id: str
    normative_debtor: str
    beneficiary: str
    content: str
    authority_id: str
    normative_source: str
    deadline: int | None
    status: ObligationStatus = ObligationStatus.CREATED
    operational_handler: str | None = None
    deadline_expired: bool = False
    evidence_receipt_ids: tuple[str, ...] = ()
    predecessor_obligation_id: str | None = None
    successor_obligation_id: str | None = None
    transfer_request_id: str | None = None
    transfer_to: str | None = None
    escalation_request_id: str | None = None
    escalation_to: str | None = None
    audit: tuple[str, ...] = ()

    @property
    def debtor(self) -> str:
        """Compatibility view; normative meaning is explicit in v0.7."""
        return self.normative_debtor

    @property
    def outstanding(self) -> bool:
        return self.status not in TERMINAL_OBLIGATION_STATUSES

    def validate_identity(self) -> None:
        for field, value in (
            ("obligation_id", self.obligation_id),
            ("normative_debtor", self.normative_debtor),
            ("beneficiary", self.beneficiary),
            ("content", self.content),
            ("authority_id", self.authority_id),
            ("normative_source", self.normative_source),
        ):
            require_nonempty_text(value, field)
        if self.deadline is not None:
            require_nonnegative_int(self.deadline, "deadline")


class ObligationRepository:
    def __init__(self) -> None:
        self._lock = RLock()
        self._tokens: dict[str, ObligationToken] = {}
        self._next_id = 1

    @property
    def tokens(self) -> Mapping[str, ObligationToken]:
        with self._lock:
            return dict(self._tokens)

    def snapshot(self) -> dict:
        with self._lock:
            return {k: asdict(v) for k, v in sorted(self._tokens.items())}

    def get(self, obligation_id: str) -> ObligationToken:
        with self._lock:
            return self._tokens[obligation_id]

    @staticmethod
    def _validate_canonical_creation(token: ObligationToken) -> None:
        token.validate_identity()
        if token.status is not ObligationStatus.CREATED:
            raise ValueError("public creation requires CREATED status")
        if token.operational_handler is not None:
            raise ValueError("public creation requires empty operational handler")
        if token.deadline_expired:
            raise ValueError("public creation cannot start expired")
        if token.evidence_receipt_ids:
            raise ValueError("public creation requires empty evidence receipts")
        if token.predecessor_obligation_id or token.successor_obligation_id:
            raise ValueError("public creation requires empty lineage")
        if token.transfer_request_id or token.transfer_to or token.escalation_request_id or token.escalation_to:
            raise ValueError("public creation requires empty transition fields")
        if token.audit:
            raise ValueError("public creation requires empty audit")

    def create(self, token: ObligationToken) -> ObligationToken:
        self._validate_canonical_creation(token)
        with self._lock:
            if token.obligation_id in self._tokens:
                raise ValueError("duplicate obligation id")
            created = replace(token, audit=("created",))
            self._tokens[token.obligation_id] = created
            return created

    def _put(self, token: ObligationToken) -> ObligationToken:
        self._tokens[token.obligation_id] = token
        return token

    def activate(self, obligation_id: str, *, actor: str) -> ObligationToken:
        with self._lock:
            token = self._tokens[obligation_id]
            if actor != token.authority_id:
                raise PermissionError("activation requires authority")
            if token.status is not ObligationStatus.CREATED:
                raise ValueError("activation requires CREATED status")
            return self._put(replace(token, status=ObligationStatus.ACTIVE, operational_handler=token.normative_debtor, audit=token.audit + ("activated",)))

    def deadline_expire(self, obligation_id: str) -> ObligationToken:
        with self._lock:
            token = self._tokens[obligation_id]
            if not token.outstanding:
                raise ValueError("terminal obligation cannot newly expire")
            return self._put(replace(token, deadline_expired=True, audit=token.audit + ("deadline_expired",)))

    def request_escalation(self, obligation_id: str, *, actor: str, request_id: str, handler: str) -> ObligationToken:
        with self._lock:
            token = self._tokens[obligation_id]
            if token.status is not ObligationStatus.ACTIVE:
                raise ValueError("escalation applies only to active obligation")
            if actor not in {token.normative_debtor, token.authority_id}:
                raise PermissionError("only normative debtor or authority may request escalation")
            return self._put(replace(
                token,
                escalation_request_id=require_nonempty_text(request_id, "request_id"),
                escalation_to=require_nonempty_text(handler, "handler"),
                audit=token.audit + (f"escalation_requested:{request_id}:{handler}",),
            ))

    def accept_escalation(self, obligation_id: str, *, receipt: HandoffAcceptanceReceipt) -> ObligationToken:
        with self._lock:
            token = self._tokens[obligation_id]
            if token.escalation_request_id is None or token.escalation_to is None:
                raise ValueError("no escalation request is pending")
            receipt.validate(request_id=token.escalation_request_id, obligation_id=token.obligation_id, transferee=token.escalation_to)
            return self._put(replace(
                token,
                operational_handler=token.escalation_to,
                escalation_request_id=None,
                escalation_to=None,
                audit=token.audit + (f"escalation_handler_accepted:{receipt.receipt_id}:{receipt.actor}",),
            ))

    def request_transfer(self, obligation_id: str, *, actor: str, request_id: str, transferee: str) -> ObligationToken:
        with self._lock:
            token = self._tokens[obligation_id]
            if actor != token.authority_id:
                raise PermissionError("transfer request requires authority")
            if token.status is not ObligationStatus.ACTIVE:
                raise ValueError("transfer request requires active obligation")
            return self._put(replace(
                token,
                status=ObligationStatus.TRANSFER_PENDING,
                transfer_request_id=require_nonempty_text(request_id, "request_id"),
                transfer_to=require_nonempty_text(transferee, "transferee"),
                audit=token.audit + (f"transfer_requested:{request_id}:{transferee}",),
            ))

    def accept_transfer(self, obligation_id: str, *, acceptance: HandoffAcceptanceReceipt, evidence: EvidenceReceipt) -> tuple[ObligationToken, ObligationToken]:
        with self._lock:
            token = self._tokens[obligation_id]
            if token.status is not ObligationStatus.TRANSFER_PENDING:
                raise ValueError("no transfer is pending")
            assert token.transfer_request_id is not None and token.transfer_to is not None
            acceptance.validate(request_id=token.transfer_request_id, obligation_id=token.obligation_id, transferee=token.transfer_to)
            evidence.validate_for(token=token, action="transfer", actor=token.authority_id)

            successor_id = f"obligation:{self._next_id}"
            while successor_id in self._tokens:
                self._next_id += 1
                successor_id = f"obligation:{self._next_id}"
            self._next_id += 1

            evidence_ids = token.evidence_receipt_ids + (evidence.receipt_id, acceptance.receipt_id)
            successor = ObligationToken(
                obligation_id=successor_id,
                normative_debtor=token.transfer_to,
                operational_handler=token.transfer_to,
                beneficiary=token.beneficiary,
                content=token.content,
                authority_id=token.authority_id,
                normative_source=token.normative_source,
                deadline=token.deadline,
                status=ObligationStatus.ACTIVE,
                deadline_expired=token.deadline_expired,
                evidence_receipt_ids=evidence_ids,
                predecessor_obligation_id=token.obligation_id,
                audit=(f"transferred_from:{token.obligation_id}",),
            )
            old = replace(
                token,
                status=ObligationStatus.TRANSFERRED,
                successor_obligation_id=successor_id,
                evidence_receipt_ids=evidence_ids,
                audit=token.audit + (f"transfer_accepted:{successor_id}",),
            )
            self._tokens[token.obligation_id] = old
            self._tokens[successor_id] = successor
            return old, successor

    def terminal_transition(self, obligation_id: str, *, action: str, actor: str, evidence: EvidenceReceipt) -> ObligationToken:
        status_by_action = {
            "satisfy": ObligationStatus.SATISFIED,
            "violate": ObligationStatus.VIOLATED,
            "release": ObligationStatus.RELEASED,
            "cancel": ObligationStatus.CANCELLED,
            "impossible": ObligationStatus.IMPOSSIBLE,
        }
        if action not in status_by_action:
            raise ValueError("unknown terminal action")
        with self._lock:
            token = self._tokens[obligation_id]
            if token.status is not ObligationStatus.ACTIVE:
                raise ValueError("terminal transition requires active obligation")
            if actor != token.authority_id:
                raise PermissionError("terminal transition requires authority")
            evidence.validate_for(token=token, action=action, actor=actor)
            return self._put(replace(
                token,
                status=status_by_action[action],
                evidence_receipt_ids=token.evidence_receipt_ids + (evidence.receipt_id,),
                audit=token.audit + (f"{action}:{evidence.receipt_id}",),
            ))


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------


def run_formal_checks() -> dict:
    checks: dict[str, bool] = {}

    # Prefix ordering.
    ledger = AuthorityCutLedger(start_cut=3)
    late_cut_rejected = False
    try:
        ledger.commit_cut(5, (AuthorityEvent("use5", AuthorityEventKind.INVOCATION, "cap", 1, 5, "req5", "dig5", "eff5"),))
    except ValueError:
        late_cut_rejected = True
    checks["out_of_order_cut_rejected_before_mutation"] = late_cut_rejected and ledger.snapshot()["raw_events"] == {}

    # Atomic failed batch.
    ledger2 = AuthorityCutLedger(start_cut=0)
    before = ledger2.snapshot()
    try:
        ledger2.commit_cut(0, (
            AuthorityEvent("e1", AuthorityEventKind.INVOCATION, "cap", 1, 0, "same", "d1", "x1"),
            AuthorityEvent("e2", AuthorityEventKind.INVOCATION, "cap", 1, 0, "same", "d2", "x2"),
        ))
    except ValueError:
        pass
    checks["failed_cut_atomic"] = ledger2.snapshot() == before

    # Obligation creation and handler distinction.
    repo = ObligationRepository()
    token = repo.create(ObligationToken("o", "debtor", "beneficiary", "content", "authority", "rule", 10))
    token = repo.activate("o", actor="authority")
    token = repo.request_escalation("o", actor="debtor", request_id="esc", handler="supervisor")
    token = repo.accept_escalation("o", receipt=HandoffAcceptanceReceipt("acc", "esc", "o", "supervisor", "supervisor", "prov"))
    checks["escalation_changes_handler_not_normative_debtor"] = token.normative_debtor == "debtor" and token.operational_handler == "supervisor"

    # Proposal claim ceiling.
    branches = BranchRepository()
    branches.add_configuration(BranchConfiguration("A", frozenset({"a"})))
    branches.add_configuration(BranchConfiguration("B", frozenset({"b"})))
    proposal, _ = branches.record_reconciliation_proposal(record_id="r", left_id="A", right_id="B", proposed_successor_id="missing")
    checks["reconciliation_is_explicitly_proposal_only"] = not proposal.semantic_validity_claim

    liveness = explore_branch_workflow()
    checks["bounded_liveness"] = liveness["pass"]
    return {"checks": checks, "liveness": liveness, "pass": all(checks.values())}


if __name__ == "__main__":
    import json

    print(json.dumps(run_formal_checks(), ensure_ascii=False, indent=2, default=str))
