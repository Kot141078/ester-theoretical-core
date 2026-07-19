from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from analysis_v08 import AnalysisPlanRegistry, default_plan
from common_v08 import DecisionKind, EvidenceStatus, ObligationStatus, sha256_digest
from endpoint_v08 import AssignmentManifest, AssignmentRegistry, DEFAULT_SCORING_CONFIG, OpportunitySpec
from epistemic_v08 import ActionOption, EpistemicState, Evidence, ModelRisk, decide_soc, register_evidence
from formal_v08 import (
    AuthorityCutLedger,
    AuthorityEvent,
    AuthorityEventKind,
    BranchConfiguration,
    BranchRepository,
    ObligationRepository,
    ObligationToken,
    HandoffAcceptanceReceipt,
    AuthorityDecision,
)
from mutation_v08 import classify_mutant_process
from sioc_v08 import CapabilityRecord, ControlRequest, InvocationContext, ReferenceMonitor, default_registry


def inv(event_id="u", cut=0, request_id="r"):
    return AuthorityEvent(event_id, AuthorityEventKind.INVOCATION, "cap", 1, cut, request_id, f"digest:{request_id}", f"effect:{request_id}")


def test_m01_prefix_guard():
    ledger = AuthorityCutLedger(start_cut=0)
    with pytest.raises(ValueError):
        ledger.commit_cut(1, (inv(cut=1),))
    assert ledger.raw_events == (), "MUTANT_M01_PREFIX_GUARD"


def test_m02_duplicate_request_prevalidation():
    ledger = AuthorityCutLedger(start_cut=0)
    before = ledger.snapshot()
    with pytest.raises(ValueError):
        ledger.commit_cut(0, (inv("a", 0, "same"), inv("b", 0, "same")))
    assert ledger.snapshot() == before, "MUTANT_M02_ATOMIC_CUT"


def test_m03_creation_guard():
    repo = ObligationRepository()
    dirty = ObligationToken("o", "d", "b", "c", "a", "rule", 1, status=ObligationStatus.CANCELLED)
    with pytest.raises(ValueError):
        repo.create(dirty)
    assert repo.snapshot() == {}, "MUTANT_M03_CREATION_GUARD"


def test_m04_escalation_handler_only():
    repo = ObligationRepository()
    repo.create(ObligationToken("o", "d", "b", "c", "a", "rule", 1))
    repo.activate("o", actor="a")
    repo.request_escalation("o", actor="d", request_id="q", handler="h")
    token = repo.accept_escalation("o", receipt=HandoffAcceptanceReceipt("x", "q", "o", "h", "h", "p"))
    assert token.normative_debtor == "d" and token.operational_handler == "h", "MUTANT_M04_ESCALATION_TRANSFER"


def test_m05_evidence_content_binding():
    state = register_evidence(EpistemicState(), Evidence("e", "p", "s", Decimal("0.9"), EvidenceStatus.PROVISIONAL, "x"), actor="a", reason="r")
    with pytest.raises(ValueError):
        register_evidence(state, Evidence("e", "q", "s", Decimal("0.9"), EvidenceStatus.PROVISIONAL, "x"), actor="a", reason="r")
    assert state.evidence_map()["e"].claim == "p", "MUTANT_M05_EVIDENCE_BINDING"


def test_m06_soc_no_unmodeled_action():
    actions = (ActionOption("A", DecisionKind.DOMAIN),)
    models = (ModelRisk("m", (("A", Decimal("100")),)),)
    decision = decide_soc(actions=actions, models=models, hard_loss_limit=Decimal("1"))
    assert decision.decision is None, "MUTANT_M06_SOC_UNIVERSE"


def test_m07_request_digest_binding():
    cap = CapabilityRecord("cap", 1, "agent", frozenset({"actuate"}), True, 10)
    monitor = ReferenceMonitor({"cap": cap}, default_registry(), server_cut=2, server_time=2)
    bad = ControlRequest(InvocationContext("agent", "cap", 1, "observe_passive", "n", "r", 2), "ACTUATE", "t", "actuator:generic", "v1")
    good = replace(bad, context=replace(bad.context, declared_scope="actuate"))
    first = monitor.execute(bad)
    second = monitor.execute(good)
    assert first.status == "REJECTED" and second.status == "REQUEST_ID_MISMATCH", "MUTANT_M07_REQUEST_BINDING"


def test_m08_assignment_registry_binding():
    original = AssignmentManifest("a", "b", "T", "v", (OpportunitySpec("x", "SRR"),), DEFAULT_SCORING_CONFIG.digest)
    registry = AssignmentRegistry((original,))
    altered = replace(original, arm="C")
    with pytest.raises(ValueError):
        registry.verify(altered)
    assert registry.digests["a"] == original.digest, "MUTANT_M08_ASSIGNMENT_BINDING"


def test_m09_plan_registry_binding():
    original = default_plan(("b1", "b2"), DEFAULT_SCORING_CONFIG.digest)
    registry = AnalysisPlanRegistry((original,))
    altered = replace(original, family_alpha=0.1)
    with pytest.raises(ValueError):
        registry.verify(altered)
    assert registry.digests[original.plan_id] == original.digest, "MUTANT_M09_PLAN_BINDING"


def test_m10_authority_required_before_effect():
    cap = CapabilityRecord("cap", 1, "agent", frozenset({"actuate"}), True, 10)
    ledger = AuthorityCutLedger(start_cut=2)
    ledger.commit_cut(2, ())
    monitor = ReferenceMonitor(
        {"cap": cap}, default_registry(), server_cut=2, server_time=2,
        trusted_prefix=ledger.prefix_snapshot(),
    )
    req = ControlRequest(InvocationContext("agent", "cap", 1, "actuate", "n", "r", 2), "ACTUATE", "t", "actuator:generic", "v1")
    receipt = monitor.execute(req)
    assert receipt.status == "REJECTED" and monitor.physical_effects == (), "MUTANT_M10_AUTHORITY_EFFECT"


def test_m11_secondary_range_validation():
    # The independent implementation is exercised by its public validation grid elsewhere;
    # this target anchors the production snippet for mutation attribution.
    from analysis_independent_v08 import _validate_value
    with pytest.raises(ValueError):
        _validate_value("SRR", -1.0)
    assert True, "MUTANT_M11_SECONDARY_VALIDATION"


def test_m12_unrelated_failure_is_error_not_kill():
    result = classify_mutant_process(exit_code=1, output="ValueError: unrelated setup failure", expected_marker="MUTANT_EXPECTED", target_node="test_target")
    assert result == "ERROR", "MUTANT_M12_ATTRIBUTION"


def test_m13_reconciliation_is_proposal_only():
    repo = BranchRepository()
    repo.add_configuration(BranchConfiguration("A", frozenset({"a"})))
    repo.add_configuration(BranchConfiguration("B", frozenset({"b"})))
    record, _ = repo.record_reconciliation_proposal(record_id="r", left_id="A", right_id="B", proposed_successor_id="missing")
    assert record.semantic_validity_claim is False, "MUTANT_M13_RECONCILIATION_CEILING"


def test_m14_empty_cut_closure():
    ledger = AuthorityCutLedger(start_cut=0)
    assert ledger.commit_cut(0, ()) == (), "MUTANT_M14_EMPTY_CUT"
    assert ledger.closed_prefix_watermark == 0 and ledger.next_cut == 1, "MUTANT_M14_EMPTY_CUT"


def test_m15_trusted_prefix_binding():
    req = ControlRequest(InvocationContext("agent", "cap", 1, "actuate", "n", "r", 2), "ACTUATE", "t", "actuator:generic", "v1")
    ledger = AuthorityCutLedger(start_cut=2)
    decision = ledger.commit_cut(2, (AuthorityEvent("u", AuthorityEventKind.INVOCATION, "cap", 1, 2, "r", req.request_digest, req.expected_effect_id),))[0]
    snapshot = ledger.prefix_snapshot()
    payload = {
        "decision_id": decision.decision_id,
        "request_id": decision.request_id,
        "request_digest": decision.request_digest,
        "capability_id": decision.capability_id,
        "capability_version": decision.capability_version,
        "invocation_cut": decision.invocation_cut,
        "closed_prefix_digest": "foreign-prefix",
        "authority_source_id": decision.authority_source_id,
        "earliest_revocation_cut": decision.earliest_revocation_cut,
        "status": decision.status,
        "effect_id": decision.effect_id,
        "reason": decision.reason,
        "raw_event_ids": decision.raw_event_ids,
    }
    foreign = AuthorityDecision(**payload, decision_digest=sha256_digest(payload))
    cap = CapabilityRecord("cap", 1, "agent", frozenset({"actuate"}), True, 10)
    monitor = ReferenceMonitor({"cap": cap}, default_registry(), server_cut=2, server_time=2, trusted_prefix=snapshot)
    receipt = monitor.execute(req, authority_decision=foreign)
    assert receipt.status == "REJECTED" and monitor.physical_effects == (), "MUTANT_M15_PREFIX_BINDING"


def test_m16_full_execution_receipt_required():
    from finalize_reports_v08 import CURRENT_EXPECTED_TESTS, LEGACY_EXPECTED_TESTS, build_unit_test_report

    def receipt(suite, expected, failures=0):
        payload = {
            "schema": "esther.rp001.v0.8.pytest_receipt.v1",
            "suite": suite,
            "python_executable": "python",
            "pythonpath": "CODE",
            "command": ["python", "-m", "pytest"],
            "full_pytest_exit_code": 0 if failures == 0 else 1,
            "expected_tests": expected,
            "collected_count": expected,
            "executed_count": expected,
            "passed_count": expected - failures,
            "failed_count": failures,
            "error_count": 0,
            "skipped_count": 0,
            "execution_mode": "full_pytest_junit",
            "junit_path": "x",
            "junit_sha256": "x",
            "stdout_path": "x",
            "stdout_sha256": "x",
            "stderr_path": "x",
            "stderr_sha256": "x",
            "stdout_tail": "",
            "stderr_tail": "",
            "pass": failures == 0,
        }
        payload["receipt_digest"] = sha256_digest(payload)
        return payload

    report = build_unit_test_report(
        receipt("TESTS", CURRENT_EXPECTED_TESTS, 1),
        receipt("LEGACY_V07/TESTS", LEGACY_EXPECTED_TESTS),
    )
    assert report["pass"] is False, "MUTANT_M16_FULL_TEST_EVIDENCE"
