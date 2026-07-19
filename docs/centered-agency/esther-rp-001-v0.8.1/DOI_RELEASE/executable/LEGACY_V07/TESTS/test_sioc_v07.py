from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from formal_v07 import AuthorityCutLedger, AuthorityEvent, AuthorityEventKind
from sioc_store_v07 import SQLiteReferenceMonitor
from sioc_v07 import (
    CapabilityRecord,
    ControlRequest,
    EffectClass,
    InvocationContext,
    MeasurementAccounting,
    OperationDescriptor,
    OperationRegistry,
    ReferenceMonitor,
    default_registry,
    run_sioc_checks,
    validate_density_matrix,
    validate_instrument,
)


def capability(scopes=frozenset({"observe_passive", "actuate", "measure_active", "measure_quantum"})):
    return CapabilityRecord("cap", 1, "agent", scopes, True, 10)


def request(
    *,
    request_id="r",
    nonce="n",
    scope="actuate",
    command="ACTUATE",
    instrument="actuator:generic",
    version="v1",
    cut=2,
):
    return ControlRequest(InvocationContext("agent", "cap", 1, scope, nonce, request_id, cut), command, "target", instrument, version)


def decision_for(req: ControlRequest, *, authorized=True):
    ledger = AuthorityCutLedger(start_cut=req.context.asserted_cut)
    events = []
    if not authorized:
        events.append(AuthorityEvent("rev", AuthorityEventKind.REVOCATION, "cap", 1, req.context.asserted_cut))
    events.append(
        AuthorityEvent(
            "use",
            AuthorityEventKind.INVOCATION,
            "cap",
            1,
            req.context.asserted_cut,
            req.context.request_id,
            req.request_digest,
            req.expected_effect_id,
        )
    )
    return ledger.commit_cut(req.context.asserted_cut, tuple(events))[0]


@pytest.mark.parametrize(
    "descriptor",
    [
        OperationDescriptor("BAD", "i", "v", EffectClass.NONE, Decimal("1"), "observe_passive"),
        OperationDescriptor("BAD", "i", "v", EffectClass.NONE, Decimal("0"), "actuate"),
        OperationDescriptor("BAD", "i", "v", EffectClass.PHYSICAL, Decimal("0"), "actuate"),
        OperationDescriptor("BAD", "i", "v", EffectClass.PHYSICAL, Decimal("1"), "observe_passive"),
    ],
)
def test_registry_rejects_inconsistent_effect_descriptors(descriptor):
    with pytest.raises(ValueError):
        OperationRegistry((descriptor,))


def test_passive_read_has_no_effect_and_needs_no_authority_decision():
    monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
    req = request(scope="observe_passive", command="READ_PASSIVE", instrument="instrument:passive")
    receipt = monitor.execute(req)
    assert receipt.status == "OBSERVED"
    assert receipt.effect_id is None
    assert monitor.physical_effects == ()
    assert receipt.verify_digest()


def test_effectful_operation_requires_matching_authority_decision():
    monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
    req = request()
    missing = monitor.execute(req)
    assert missing.status == "REJECTED"
    assert missing.reason == "AUTHORITY_DECISION_MISSING"
    assert monitor.physical_effects == ()


def test_matching_authority_decision_applies_one_effect():
    monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
    req = request()
    receipt = monitor.execute(req, authority_decision=decision_for(req))
    assert receipt.status == "APPLIED"
    assert receipt.effect_id == "effect:r"
    assert receipt.authority_decision_digest is not None
    assert monitor.physical_effects == ("effect:r",)


def test_rejected_or_mismatched_authority_decisions_fail_closed():
    req = request()
    cases = [
        decision_for(req, authorized=False),
        replace(decision_for(req), request_digest="different"),
        replace(decision_for(req), capability_version=2),
        replace(decision_for(req), invocation_cut=3),
        replace(decision_for(req), effect_id="effect:other"),
    ]
    expected_reasons = {
        "AUTHORITY_DECISION_REJECTED",
        "AUTHORITY_DECISION_DIGEST_INVALID",
        "AUTHORITY_DECISION_BINDING_MISMATCH",
    }
    for idx, decision in enumerate(cases):
        monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
        receipt = monitor.execute(replace(req, context=replace(req.context, request_id=f"r{idx}", nonce=f"n{idx}"))) if False else None
        # Rebuild request/decision pair only for the original identity; mutated decision must fail.
        receipt = monitor.execute(req, authority_decision=decision)
        assert receipt.status == "REJECTED"
        assert receipt.reason in expected_reasons
        assert monitor.physical_effects == ()


def test_rejected_request_id_is_bound_to_first_digest():
    monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
    bad = request(scope="observe_passive")
    first = monitor.execute(bad)
    assert first.status == "REJECTED"
    exact = monitor.execute(bad)
    assert exact == first
    good_changed = request(scope="actuate")
    second = monitor.execute(good_changed, authority_decision=decision_for(good_changed))
    assert second.status == "REQUEST_ID_MISMATCH"
    assert monitor.physical_effects == ()
    assert len(monitor.audit) == 1


def test_successful_request_id_is_bound_to_first_digest():
    monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
    req = request()
    first = monitor.execute(req, authority_decision=decision_for(req))
    changed = request(command="DESTRUCTIVE_READ", scope="measure_active", instrument="instrument:active")
    second = monitor.execute(changed, authority_decision=decision_for(changed))
    assert first.status == "APPLIED"
    assert second.status == "REQUEST_ID_MISMATCH"
    assert monitor.physical_effects == ("effect:r",)


def test_nonce_replay_under_different_request_is_rejected():
    monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
    first = request(request_id="r1", nonce="same")
    second = request(request_id="r2", nonce="same")
    assert monitor.execute(first, authority_decision=decision_for(first)).status == "APPLIED"
    rejected = monitor.execute(second, authority_decision=decision_for(second))
    assert rejected.status == "REJECTED"
    assert rejected.reason == "NONCE_REPLAY"
    assert monitor.physical_effects == ("effect:r1",)


def test_in_memory_same_nonce_concurrency_creates_one_effect():
    monitor = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)

    def worker(i):
        req = request(request_id=f"r{i}", nonce="shared")
        return monitor.execute(req, authority_decision=decision_for(req)).status

    with ThreadPoolExecutor(max_workers=16) as pool:
        statuses = list(pool.map(worker, range(32)))
    assert statuses.count("APPLIED") == 1
    assert statuses.count("REJECTED") == 31
    assert len(monitor.physical_effects) == 1
    assert len(monitor.used_nonces) == 1


def test_capability_and_operation_validation():
    cases = [
        (capability(), request(cut=3), "STALE_OR_FUTURE_CUT"),
        (replace(capability(), active=False), request(), "CAPABILITY_INACTIVE"),
        (replace(capability(), principal="other"), request(), "PRINCIPAL_MISMATCH"),
        (replace(capability(), version=2), request(), "CAPABILITY_VERSION_MISMATCH"),
        (replace(capability(), scopes=frozenset({"observe_passive"})), request(), "SCOPE_NOT_GRANTED"),
        (replace(capability(), expiry_time=1), request(), "CAPABILITY_EXPIRED"),
    ]
    for cap, req, reason in cases:
        monitor = ReferenceMonitor({"cap": cap}, default_registry(), server_cut=2, server_time=2)
        receipt = monitor.execute(req, authority_decision=decision_for(req))
        assert receipt.status == "REJECTED"
        assert receipt.reason == reason
        assert monitor.physical_effects == ()


def sqlite_store(tmp_path: Path):
    store = SQLiteReferenceMonitor(tmp_path / "monitor.sqlite3", default_registry())
    store.initialize([capability()], server_cut=2, server_time=2)
    return store


def test_sqlite_matching_authority_and_exact_retry(tmp_path):
    store = sqlite_store(tmp_path)
    req = request()
    decision = decision_for(req)
    first = store.execute(req, authority_decision=decision)
    second = store.execute(req, authority_decision=decision)
    assert first == second
    assert store.counts() == {"requests": 1, "nonces": 1, "effects": 1, "audit": 1}


def test_sqlite_rejected_request_binding(tmp_path):
    store = sqlite_store(tmp_path)
    bad = request(scope="observe_passive")
    first = store.execute(bad)
    changed = request(scope="actuate")
    second = store.execute(changed, authority_decision=decision_for(changed))
    assert first.status == "REJECTED"
    assert second.status == "REQUEST_ID_MISMATCH"
    assert store.counts()["effects"] == 0


def test_sqlite_no_authority_no_effect(tmp_path):
    store = sqlite_store(tmp_path)
    receipt = store.execute(request())
    assert receipt.reason == "AUTHORITY_DECISION_MISSING"
    assert store.counts()["effects"] == 0


def test_sqlite_same_nonce_thread_concurrency(tmp_path):
    store = sqlite_store(tmp_path)

    def worker(i):
        req = request(request_id=f"r{i}", nonce="shared")
        return store.execute(req, authority_decision=decision_for(req)).status

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(worker, range(24)))
    assert statuses.count("APPLIED") == 1
    assert statuses.count("REJECTED") == 23
    counts = store.counts()
    assert counts["effects"] == 1
    assert counts["nonces"] == 1
    assert counts["requests"] == 24


def test_sqlite_stored_receipt_tampering_detected(tmp_path):
    store = sqlite_store(tmp_path)
    req = request()
    store.execute(req, authority_decision=decision_for(req))
    conn = sqlite3.connect(store.path)
    payload = json.loads(conn.execute("SELECT receipt_json FROM requests WHERE request_id='r'").fetchone()[0])
    payload["effect_budget"] = "999"
    conn.execute("UPDATE requests SET receipt_json=? WHERE request_id='r'", (json.dumps(payload),))
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="digest mismatch"):
        store.receipt("r")


@pytest.mark.parametrize(
    "rho,expected",
    [
        (np.eye(2) / 2, True),
        (np.array([[1.0, 1.0], [0.0, 0.0]]), False),
        (np.diag([1.000005, 0.0]), False),
        (np.array([[float("nan")]]), False),
    ],
)
def test_density_matrix_validation_uses_strict_absolute_tolerance(rho, expected):
    assert validate_density_matrix(rho, atol=1e-9) is expected


def test_quantum_instrument_completeness():
    z0 = np.array([[1.0, 0.0], [0.0, 0.0]])
    z1 = np.array([[0.0, 0.0], [0.0, 1.0]])
    assert validate_instrument({"0": (z0,), "1": (z1,)})
    assert not validate_instrument({"0": (z0,)})
    assert not validate_instrument({"0": (z0,), "bad": (np.eye(3),)})


@pytest.mark.parametrize(
    "accounting,valid",
    [
        (MeasurementAccounting(2, ("0", "1")), True),
        (MeasurementAccounting(1, ("0", "1")), False),
        (MeasurementAccounting(1, ("0", "1"), no_clicks=-1), False),
        (MeasurementAccounting(2, ("0",), no_clicks=1), True),
    ],
)
def test_measurement_accounting(accounting, valid):
    assert accounting.validate() is valid


def test_aggregate_sioc_checks_pass():
    assert run_sioc_checks()["pass"]
