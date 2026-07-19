from __future__ import annotations

import sys
from dataclasses import replace
from decimal import Decimal


def fail(marker: str) -> None:
    print(marker)
    raise SystemExit(1)


def run(target: str) -> None:
    if target == "M01_PREFIX_GUARD":
        from formal_v08 import AuthorityCutLedger, AuthorityEvent, AuthorityEventKind
        ledger = AuthorityCutLedger(start_cut=0)
        try:
            ledger.commit_cut(1, (AuthorityEvent("u", AuthorityEventKind.INVOCATION, "cap", 1, 1, "r", "d", "effect:r"),))
        except ValueError:
            return
        fail("MUTANT_M01_PREFIX_GUARD")

    if target == "M02_REQUEST_PREVALIDATION":
        from formal_v08 import AuthorityCutLedger, AuthorityEvent, AuthorityEventKind
        ledger = AuthorityCutLedger(start_cut=0)
        before = ledger.snapshot()
        events = (
            AuthorityEvent("a", AuthorityEventKind.INVOCATION, "cap", 1, 0, "same", "d1", "e1"),
            AuthorityEvent("b", AuthorityEventKind.INVOCATION, "cap", 1, 0, "same", "d2", "e2"),
        )
        try:
            ledger.commit_cut(0, events)
        except ValueError:
            if ledger.snapshot() == before:
                return
        fail("MUTANT_M02_ATOMIC_CUT")

    if target == "M03_CANONICAL_CREATION":
        from common_v08 import ObligationStatus
        from formal_v08 import ObligationRepository, ObligationToken
        repo = ObligationRepository()
        token = ObligationToken("o", "d", "b", "c", "a", "rule", 1, status=ObligationStatus.CANCELLED)
        try:
            repo.create(token)
        except ValueError:
            return
        fail("MUTANT_M03_CREATION_GUARD")

    if target == "M04_ESCALATION_CHANGES_DEBTOR":
        from formal_v08 import HandoffAcceptanceReceipt, ObligationRepository, ObligationToken
        repo = ObligationRepository()
        repo.create(ObligationToken("o", "d", "b", "c", "a", "rule", 1))
        repo.activate("o", actor="a")
        repo.request_escalation("o", actor="d", request_id="q", handler="h")
        token = repo.accept_escalation("o", receipt=HandoffAcceptanceReceipt("x", "q", "o", "h", "h", "p"))
        if token.normative_debtor == "d" and token.operational_handler == "h":
            return
        fail("MUTANT_M04_ESCALATION_TRANSFER")

    if target == "M05_EVIDENCE_REBIND":
        from common_v08 import EvidenceStatus
        from epistemic_v08 import EpistemicState, Evidence, register_evidence
        state = register_evidence(EpistemicState(), Evidence("e", "p", "s", Decimal("0.9"), EvidenceStatus.PROVISIONAL, "x"), actor="a", reason="r")
        try:
            register_evidence(state, Evidence("e", "q", "s", Decimal("0.9"), EvidenceStatus.PROVISIONAL, "x"), actor="a", reason="r")
        except ValueError:
            return
        fail("MUTANT_M05_EVIDENCE_BINDING")

    if target == "M06_UNMODELED_SOC_ACTION":
        from common_v08 import DecisionKind
        from epistemic_v08 import ActionOption, ModelRisk, decide_soc
        decision = decide_soc(
            actions=(ActionOption("A", DecisionKind.DOMAIN),),
            models=(ModelRisk("m", (("A", Decimal("100")),)),),
            hard_loss_limit=Decimal("1"),
        )
        if decision.decision is None:
            return
        fail("MUTANT_M06_SOC_UNIVERSE")

    if target == "M07_REQUEST_REBIND":
        from sioc_v08 import CapabilityRecord, ControlRequest, InvocationContext, ReferenceMonitor, default_registry
        cap = CapabilityRecord("cap", 1, "agent", frozenset({"actuate"}), True, 10)
        monitor = ReferenceMonitor({"cap": cap}, default_registry(), server_cut=2, server_time=2)
        bad = ControlRequest(InvocationContext("agent", "cap", 1, "observe_passive", "n", "r", 2), "ACTUATE", "t", "actuator:generic", "v1")
        good = replace(bad, context=replace(bad.context, declared_scope="actuate"))
        first = monitor.execute(bad)
        second = monitor.execute(good)
        if first.status == "REJECTED" and second.status == "REQUEST_ID_MISMATCH":
            return
        fail("MUTANT_M07_REQUEST_BINDING")

    if target == "M08_ASSIGNMENT_DIGEST_BYPASS":
        from endpoint_v08 import AssignmentManifest, AssignmentRegistry, DEFAULT_SCORING_CONFIG, OpportunitySpec
        original = AssignmentManifest("a", "b", "T", "v", (OpportunitySpec("x", "SRR"),), DEFAULT_SCORING_CONFIG.digest)
        registry = AssignmentRegistry((original,))
        try:
            registry.verify(replace(original, arm="C"))
        except ValueError:
            return
        fail("MUTANT_M08_ASSIGNMENT_BINDING")

    if target == "M09_PLAN_DIGEST_BYPASS":
        from analysis_v08 import AnalysisPlanRegistry, default_plan
        from endpoint_v08 import DEFAULT_SCORING_CONFIG
        original = default_plan(("b1", "b2"), DEFAULT_SCORING_CONFIG.digest)
        registry = AnalysisPlanRegistry((original,))
        try:
            registry.verify(replace(original, family_alpha=0.1))
        except ValueError:
            return
        fail("MUTANT_M09_PLAN_BINDING")

    if target == "M10_AUTHORITY_OPTIONAL":
        from formal_v08 import AuthorityCutLedger
        from sioc_v08 import CapabilityRecord, ControlRequest, InvocationContext, ReferenceMonitor, default_registry
        cap = CapabilityRecord("cap", 1, "agent", frozenset({"actuate"}), True, 10)
        ledger = AuthorityCutLedger(start_cut=2)
        ledger.commit_cut(2, ())
        monitor = ReferenceMonitor(
            {"cap": cap}, default_registry(), server_cut=2, server_time=2,
            trusted_prefix=ledger.prefix_snapshot(),
        )
        req = ControlRequest(InvocationContext("agent", "cap", 1, "actuate", "n", "r", 2), "ACTUATE", "t", "actuator:generic", "v1")
        receipt = monitor.execute(req)
        if receipt.status == "REJECTED" and monitor.physical_effects == ():
            return
        fail("MUTANT_M10_AUTHORITY_EFFECT")

    if target == "M11_SECONDARY_RANGE_BYPASS":
        from analysis_independent_v08 import _validate_value
        try:
            _validate_value("SRR", -1.0)
        except ValueError:
            return
        fail("MUTANT_M11_SECONDARY_VALIDATION")

    if target == "M12_GENERIC_FAILURE_AS_KILL":
        from mutation_v08 import classify_mutant_process
        result = classify_mutant_process(exit_code=1, output="ValueError: unrelated setup failure", expected_marker="MUTANT_EXPECTED", target_node="M12_GENERIC_FAILURE_AS_KILL")
        if result == "ERROR":
            return
        fail("MUTANT_M12_ATTRIBUTION")

    if target == "M13_RECONCILIATION_CLAIM_UPGRADE":
        from formal_v08 import BranchConfiguration, BranchRepository
        repo = BranchRepository()
        repo.add_configuration(BranchConfiguration("A", frozenset({"a"})))
        repo.add_configuration(BranchConfiguration("B", frozenset({"b"})))
        record, _ = repo.record_reconciliation_proposal(record_id="r", left_id="A", right_id="B", proposed_successor_id="missing")
        if record.semantic_validity_claim is False:
            return
        fail("MUTANT_M13_RECONCILIATION_CEILING")

    if target == "M14_EMPTY_CUT_REJECT":
        from formal_v08 import AuthorityCutLedger
        ledger = AuthorityCutLedger(start_cut=0)
        try:
            result = ledger.commit_cut(0, ())
        except ValueError:
            fail("MUTANT_M14_EMPTY_CUT")
        if result == () and ledger.closed_prefix_watermark == 0 and ledger.next_cut == 1:
            return
        fail("MUTANT_M14_EMPTY_CUT")

    if target == "M15_PREFIX_BINDING_BYPASS":
        from common_v08 import sha256_digest
        from formal_v08 import AuthorityCutLedger, AuthorityDecision, AuthorityEvent, AuthorityEventKind
        from sioc_v08 import CapabilityRecord, ControlRequest, InvocationContext, ReferenceMonitor, default_registry
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
        if receipt.status == "REJECTED" and monitor.physical_effects == ():
            return
        fail("MUTANT_M15_PREFIX_BINDING")

    if target == "M16_UNIT_RECEIPT_BYPASS":
        import hashlib
        import tempfile
        from pathlib import Path
        from common_v08 import sha256_digest
        from finalize_reports_v08 import CURRENT_EXPECTED_TESTS, LEGACY_EXPECTED_TESTS, build_unit_test_report

        with tempfile.TemporaryDirectory(prefix="esther-v08-m16-") as td:
            artifact_root = Path(td)

            def receipt(suite, expected, failures=0):
                stem = suite.replace("/", "_")
                junit = artifact_root / f"{stem}.xml"
                stdout = artifact_root / f"{stem}.stdout.txt"
                stderr = artifact_root / f"{stem}.stderr.txt"
                junit.write_text(
                    f'<testsuites><testsuite tests="{expected}" failures="{failures}" errors="0" skipped="0"/></testsuites>',
                    encoding="utf-8",
                )
                stdout.write_text("evidence\n", encoding="utf-8")
                stderr.write_text("", encoding="utf-8")
                raw_hash = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
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
                    "junit_path": str(junit),
                    "junit_sha256": raw_hash(junit),
                    "stdout_path": str(stdout),
                    "stdout_sha256": raw_hash(stdout),
                    "stderr_path": str(stderr),
                    "stderr_sha256": raw_hash(stderr),
                    "stdout_tail": "",
                    "stderr_tail": "",
                    "pass": failures == 0,
                }
                payload["receipt_digest"] = sha256_digest(payload)
                return payload

            report = build_unit_test_report(
                receipt("TESTS", CURRENT_EXPECTED_TESTS, failures=1),
                receipt("LEGACY_V07/TESTS", LEGACY_EXPECTED_TESTS),
                artifact_root=artifact_root,
            )
            if report["pass"] is False:
                return
        fail("MUTANT_M16_FULL_TEST_EVIDENCE")

    raise SystemExit(f"unknown mutation target: {target}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: mutation_runner_v08.py <target>")
    run(sys.argv[1])
