from __future__ import annotations

from dataclasses import replace
from itertools import permutations
from threading import Barrier, Thread

import pytest

from common_v08 import ObligationStatus
from formal_v08 import (
    AuthorityCutLedger,
    AuthorityEvent,
    AuthorityEventKind,
    BranchConfiguration,
    BranchRepository,
    DependencyEdge,
    DependencyKind,
    EvidenceReceipt,
    HandoffAcceptanceReceipt,
    ObligationRepository,
    ObligationToken,
    ProductRefinementLedger,
    TimeInterval,
    explore_branch_workflow,
    run_formal_checks,
    validate_dependency,
)


def invocation(event_id: str, cut: int, request_id: str = "req", digest: str = "digest", effect_id: str | None = None):
    return AuthorityEvent(event_id, AuthorityEventKind.INVOCATION, "cap", 1, cut, request_id, digest, effect_id or f"effect:{request_id}")


def revocation(event_id: str, cut: int):
    return AuthorityEvent(event_id, AuthorityEventKind.REVOCATION, "cap", 1, cut)


def canonical_token(**changes):
    base = ObligationToken("o", "debtor", "beneficiary", "content", "authority", "rule", 10)
    return replace(base, **changes)


def active_repo():
    repo = ObligationRepository()
    repo.create(canonical_token())
    repo.activate("o", actor="authority")
    return repo


def evidence(action: str, obligation_id: str = "o", actor: str = "authority"):
    return EvidenceReceipt(f"ev:{action}", actor, "authority", action, obligation_id, "reason", ("ref",), "prov")


def acceptance(request_id: str, obligation_id: str, transferee: str, actor: str | None = None):
    actor = transferee if actor is None else actor
    return HandoffAcceptanceReceipt(f"acc:{request_id}", request_id, obligation_id, actor, transferee, "prov")


def test_dependency_physical_requires_known_order():
    edge = DependencyEdge("a", "b", DependencyKind.PHYSICAL_CAUSE, TimeInterval(0, 1), TimeInterval(1, 2))
    assert validate_dependency(edge)


@pytest.mark.parametrize(
    "edge",
    [
        DependencyEdge("a", "a", DependencyKind.INFORMATIONAL, TimeInterval(None, None), TimeInterval(None, None)),
        DependencyEdge("a", "b", DependencyKind.PHYSICAL_CAUSE, TimeInterval(None, None), TimeInterval(1, 2)),
        DependencyEdge("a", "b", DependencyKind.PHYSICAL_CAUSE, TimeInterval(2, 3), TimeInterval(1, 2)),
    ],
)
def test_invalid_dependencies(edge):
    assert not validate_dependency(edge)


def test_prefix_requires_declared_start_cut():
    ledger = AuthorityCutLedger(start_cut=3)
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="out-of-order"):
        ledger.commit_cut(5, (invocation("e5", 5),))
    assert ledger.snapshot() == before


def test_empty_cut_closes_prefix_and_is_idempotent():
    ledger = AuthorityCutLedger(start_cut=0)
    before = ledger.snapshot()
    result = ledger.commit_cut(0, ())
    assert result == ()
    assert ledger.next_cut == 1
    assert ledger.closed_prefix_watermark == 0
    assert ledger.raw_events == ()
    assert ledger.decisions == ()
    snapshot = ledger.snapshot()
    assert snapshot != before
    assert ledger.commit_cut(0, ()) == ()
    assert ledger.snapshot() == snapshot

    with pytest.raises(ValueError, match="different batch"):
        ledger.commit_cut(0, (invocation("late", 0),))
    assert ledger.snapshot() == snapshot


def test_empty_cut_can_bridge_to_later_nonempty_cut():
    ledger = AuthorityCutLedger(start_cut=3)
    ledger.commit_cut(3, ())
    decision = ledger.commit_cut(4, (invocation("u4", 4),))[0]
    assert ledger.closed_prefix_watermark == 4
    assert decision.status == "AUTHORIZED"
    assert decision.closed_prefix_digest == ledger.closed_prefix_digest


def test_prefix_closes_contiguously_and_tracks_watermark():
    ledger = AuthorityCutLedger(start_cut=3)
    assert ledger.closed_prefix_watermark is None
    ledger.commit_cut(3, (revocation("r3", 3),))
    assert ledger.closed_prefix_watermark == 3
    decision = ledger.commit_cut(4, (invocation("u4", 4),))[0]
    assert ledger.closed_prefix_watermark == 4
    assert decision.status == "REJECTED"


def test_use_before_later_revocation_is_authorized():
    ledger = AuthorityCutLedger(start_cut=4)
    decision = ledger.commit_cut(4, (invocation("u4", 4),))[0]
    ledger.commit_cut(5, (revocation("r5", 5),))
    assert decision.status == "AUTHORIZED"
    assert ledger.decision_for("req") == decision


def test_late_earlier_revocation_is_rejected_before_mutation():
    ledger = AuthorityCutLedger(start_cut=5)
    ledger.commit_cut(5, (invocation("u5", 5),))
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="out-of-order"):
        ledger.commit_cut(3, (revocation("r3", 3),))
    assert ledger.snapshot() == before


@pytest.mark.parametrize("order", list(permutations(("inv", "rev"))))
def test_equal_cut_permutations_fail_closed(order):
    events = {
        "inv": invocation("u", 0),
        "rev": revocation("r", 0),
    }
    ledger = AuthorityCutLedger(start_cut=0)
    decision = ledger.commit_cut(0, tuple(events[x] for x in order))[0]
    assert decision.status == "REJECTED"
    assert decision.effect_id is None
    assert decision.verify_digest()


def test_cut_exact_retry_is_idempotent():
    ledger = AuthorityCutLedger(start_cut=0)
    events = (invocation("u", 0),)
    assert ledger.commit_cut(0, events) == ledger.commit_cut(0, events)
    assert len(ledger.raw_events) == 1
    assert len(ledger.decisions) == 1


def test_cut_changed_retry_rejected_without_mutation():
    ledger = AuthorityCutLedger(start_cut=0)
    ledger.commit_cut(0, (invocation("u", 0),))
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="different batch"):
        ledger.commit_cut(0, (revocation("r", 0),))
    assert ledger.snapshot() == before


@pytest.mark.parametrize(
    "events,error",
    [
        ((invocation("same", 0, "a"), invocation("same", 0, "b")), "duplicate event"),
        ((invocation("a", 0, "same"), invocation("b", 0, "same")), "duplicate request"),
        ((invocation("a", 0, "r1"), AuthorityEvent("bad", AuthorityEventKind.INVOCATION, "cap", 1, 1, "r2", "d", "e")), "belong"),
    ],
)
def test_failed_cut_validation_is_atomic(events, error):
    ledger = AuthorityCutLedger(start_cut=0)
    before = ledger.snapshot()
    with pytest.raises(ValueError, match=error):
        ledger.commit_cut(0, events)
    assert ledger.snapshot() == before


def test_cross_cut_request_collision_is_atomic():
    ledger = AuthorityCutLedger(start_cut=0)
    ledger.commit_cut(0, (invocation("u0", 0, "same"),))
    before = ledger.snapshot()
    with pytest.raises(ValueError, match="already decided"):
        ledger.commit_cut(1, (invocation("u1", 1, "same"),))
    assert ledger.snapshot() == before


def test_prefix_digest_changes_and_is_bound_to_decision():
    ledger = AuthorityCutLedger(start_cut=0)
    initial = ledger.closed_prefix_digest
    decision = ledger.commit_cut(0, (invocation("u", 0),))[0]
    assert ledger.closed_prefix_digest != initial
    assert decision.closed_prefix_digest == ledger.closed_prefix_digest
    assert decision.verify_digest()


def test_reconciliation_proposal_requires_existing_sources():
    repo = BranchRepository()
    repo.add_configuration(BranchConfiguration("A", frozenset({"a"})))
    with pytest.raises(KeyError):
        repo.record_reconciliation_proposal(record_id="r", left_id="A", right_id="B", proposed_successor_id="S")


def test_reconciliation_proposal_is_explicitly_nonsemantic():
    repo = BranchRepository()
    repo.add_configuration(BranchConfiguration("A", frozenset({"a"})))
    repo.add_configuration(BranchConfiguration("B", frozenset({"b"})))
    record, created = repo.record_reconciliation_proposal(
        record_id="r",
        left_id="A",
        right_id="B",
        proposed_successor_id="missing",
        mapping=(),
    )
    assert created
    assert not record.semantic_validity_claim
    assert record.proposed_successor_id == "missing"


def test_reconciliation_proposal_retry_is_idempotent_and_changed_content_fails():
    repo = BranchRepository()
    repo.add_configuration(BranchConfiguration("A", frozenset({"a"})))
    repo.add_configuration(BranchConfiguration("B", frozenset({"b"})))
    first, created = repo.record_reconciliation_proposal(record_id="r", left_id="A", right_id="B", proposed_successor_id="S")
    second, created2 = repo.record_reconciliation_proposal(record_id="r", left_id="B", right_id="A", proposed_successor_id="S")
    assert created and not created2 and first == second
    with pytest.raises(ValueError):
        repo.record_reconciliation_proposal(record_id="r", left_id="A", right_id="B", proposed_successor_id="T")


def test_concurrent_reconciliation_proposal_creates_once():
    repo = BranchRepository()
    repo.add_configuration(BranchConfiguration("A", frozenset({"a"})))
    repo.add_configuration(BranchConfiguration("B", frozenset({"b"})))
    barrier = Barrier(8)
    results = []

    def worker():
        barrier.wait()
        results.append(repo.record_reconciliation_proposal(record_id="r", left_id="A", right_id="B", proposed_successor_id="S"))

    threads = [Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(created for _, created in results) == 1
    assert len(repo.reconciliation_proposals) == 1


def test_rejection_receipt_is_idempotent_and_changed_digest_fails():
    ledger = ProductRefinementLedger()
    a = ledger.reject(request_id="r", request_digest="d", reason="NO_AUTH")
    b = ledger.reject(request_id="r", request_digest="d", reason="NO_AUTH")
    assert a == b
    assert len(ledger.audit_events) == 1
    assert ledger.physical_effects == ()
    with pytest.raises(ValueError):
        ledger.reject(request_id="r", request_digest="other", reason="NO_AUTH")


def test_bounded_liveness_and_infinite_defer_mutant():
    good = explore_branch_workflow()
    bad = explore_branch_workflow(mutant="infinite_defer")
    assert good["pass"]
    assert good["observed_worst_case_ticks"] == 6
    assert good["declared_ceiling_ticks"] == 8
    assert bad["nonterminal_cycle"]


@pytest.mark.parametrize("status", list(ObligationStatus))
def test_public_creation_accepts_only_created(status):
    repo = ObligationRepository()
    token = canonical_token(status=status)
    if status is ObligationStatus.CREATED:
        assert repo.create(token).status is ObligationStatus.CREATED
    else:
        with pytest.raises(ValueError, match="CREATED"):
            repo.create(token)


@pytest.mark.parametrize(
    "changes",
    [
        {"operational_handler": "h"},
        {"deadline_expired": True},
        {"evidence_receipt_ids": ("e",)},
        {"predecessor_obligation_id": "p"},
        {"successor_obligation_id": "s"},
        {"transfer_request_id": "t"},
        {"transfer_to": "x"},
        {"escalation_request_id": "e"},
        {"escalation_to": "x"},
        {"audit": ("dirty",)},
    ],
)
def test_dirty_creation_rejected(changes):
    repo = ObligationRepository()
    with pytest.raises(ValueError):
        repo.create(canonical_token(**changes))
    assert repo.snapshot() == {}


def test_escalation_changes_only_operational_handler():
    repo = active_repo()
    repo.request_escalation("o", actor="debtor", request_id="esc", handler="supervisor")
    token = repo.accept_escalation("o", receipt=acceptance("esc", "o", "supervisor"))
    assert token.normative_debtor == "debtor"
    assert token.operational_handler == "supervisor"
    assert token.outstanding


def test_intruder_cannot_accept_escalation():
    repo = active_repo()
    repo.request_escalation("o", actor="debtor", request_id="esc", handler="supervisor")
    before = repo.snapshot()
    with pytest.raises(PermissionError):
        repo.accept_escalation("o", receipt=acceptance("esc", "o", "supervisor", actor="intruder"))
    assert repo.snapshot() == before


def test_transfer_requires_authority_request_and_named_acceptance():
    repo = active_repo()
    with pytest.raises(PermissionError):
        repo.request_transfer("o", actor="debtor", request_id="tr", transferee="new")
    repo.request_transfer("o", actor="authority", request_id="tr", transferee="new")
    before = repo.snapshot()
    with pytest.raises(PermissionError):
        repo.accept_transfer("o", acceptance=acceptance("tr", "o", "new", actor="intruder"), evidence=evidence("transfer"))
    assert repo.snapshot() == before


def test_transfer_generates_unique_successor_and_preserves_continuity():
    repo = active_repo()
    repo.deadline_expire("o")
    repo.request_transfer("o", actor="authority", request_id="tr", transferee="new")
    old, new = repo.accept_transfer("o", acceptance=acceptance("tr", "o", "new"), evidence=evidence("transfer"))
    assert old.status is ObligationStatus.TRANSFERRED
    assert old.obligation_id != new.obligation_id
    assert old.successor_obligation_id == new.obligation_id
    assert new.predecessor_obligation_id == old.obligation_id
    assert new.normative_debtor == "new"
    assert new.deadline == old.deadline
    assert new.deadline_expired
    assert new.normative_source == old.normative_source
    assert len(new.evidence_receipt_ids) == 2


@pytest.mark.parametrize(
    "action,expected",
    [
        ("satisfy", ObligationStatus.SATISFIED),
        ("violate", ObligationStatus.VIOLATED),
        ("release", ObligationStatus.RELEASED),
        ("cancel", ObligationStatus.CANCELLED),
        ("impossible", ObligationStatus.IMPOSSIBLE),
    ],
)
def test_terminal_transitions_require_bound_evidence(action, expected):
    repo = active_repo()
    token = repo.terminal_transition("o", action=action, actor="authority", evidence=evidence(action))
    assert token.status is expected
    assert token.evidence_receipt_ids == (f"ev:{action}",)


def test_unauthorized_terminal_transition_does_not_mutate():
    repo = active_repo()
    before = repo.snapshot()
    with pytest.raises(PermissionError):
        repo.terminal_transition("o", action="cancel", actor="intruder", evidence=evidence("cancel", actor="intruder"))
    assert repo.snapshot() == before


def test_aggregate_formal_checks_pass():
    assert run_formal_checks()["pass"]
