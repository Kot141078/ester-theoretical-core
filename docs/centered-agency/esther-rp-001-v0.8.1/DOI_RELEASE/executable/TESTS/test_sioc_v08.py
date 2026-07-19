from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from common_v08 import sha256_digest
from formal_v08 import (
    AuthorityCutLedger,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityEventKind,
    AuthorityPrefixSnapshot,
)
from sioc_store_v08 import SQLiteReferenceMonitor
from sioc_v08 import (
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
    return ControlRequest(
        InvocationContext("agent", "cap", 1, scope, nonce, request_id, cut),
        command,
        "target",
        instrument,
        version,
    )


def authority_bundle(*requests: ControlRequest, authorized: bool = True):
    if not requests:
        raise ValueError("at least one request is required")
    cuts = {req.context.asserted_cut for req in requests}
    if len(cuts) != 1:
        raise ValueError("all requests must share one cut")
    cut = next(iter(cuts))
    ledger = AuthorityCutLedger(start_cut=cut)
    events = []
    if not authorized:
        events.append(AuthorityEvent("rev", AuthorityEventKind.REVOCATION, "cap", 1, cut))
    for index, req in enumerate(requests):
        events.append(
            AuthorityEvent(
                f"use:{index}:{req.context.request_id}",
                AuthorityEventKind.INVOCATION,
                "cap",
                1,
                cut,
                req.context.request_id,
                req.request_digest,
                req.expected_effect_id,
            )
        )
    decisions = ledger.commit_cut(cut, tuple(events))
    return {decision.request_id: decision for decision in decisions}, ledger.prefix_snapshot()


def authority_for(req: ControlRequest, *, authorized: bool = True):
    decisions, snapshot = authority_bundle(req, authorized=authorized)
    return decisions[req.context.request_id], snapshot


def empty_prefix(cut: int = 2) -> AuthorityPrefixSnapshot:
    ledger = AuthorityCutLedger(start_cut=cut)
    ledger.commit_cut(cut, ())
    return ledger.prefix_snapshot()


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


def test_effectful_operation_requires_trusted_prefix_and_decision():
    req = request()
    no_prefix = ReferenceMonitor({"cap": capability()}, default_registry(), server_cut=2, server_time=2)
    missing_prefix = no_prefix.execute(req)
    assert missing_prefix.status == "REJECTED"
    assert missing_prefix.reason == "AUTHORITY_PREFIX_MISSING"

    _, snapshot = authority_for(req)
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=snapshot
    )
    missing_decision = monitor.execute(req)
    assert missing_decision.status == "REJECTED"
    assert missing_decision.reason == "AUTHORITY_DECISION_MISSING"
    assert monitor.physical_effects == ()


def test_matching_authority_decision_applies_one_effect():
    req = request()
    decision, snapshot = authority_for(req)
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=snapshot
    )
    receipt = monitor.execute(req, authority_decision=decision)
    assert receipt.status == "APPLIED"
    assert receipt.effect_id == "effect:r"
    assert receipt.authority_decision_digest == decision.decision_digest
    assert receipt.authority_prefix_digest == snapshot.closed_prefix_digest
    assert receipt.authority_source_id == snapshot.authority_source_id
    assert monitor.physical_effects == ("effect:r",)


def test_foreign_prefix_digest_is_rejected_in_memory():
    req = request()
    decision, trusted = authority_for(req)
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
    assert foreign.verify_digest()
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=trusted
    )
    receipt = monitor.execute(req, authority_decision=foreign)
    assert receipt.status == "REJECTED"
    assert receipt.reason == "AUTHORITY_PREFIX_MISMATCH"
    assert monitor.physical_effects == ()


def test_foreign_authority_source_is_rejected_in_memory():
    req = request()
    decision, trusted = authority_for(req)
    payload = {
        "decision_id": decision.decision_id,
        "request_id": decision.request_id,
        "request_digest": decision.request_digest,
        "capability_id": decision.capability_id,
        "capability_version": decision.capability_version,
        "invocation_cut": decision.invocation_cut,
        "closed_prefix_digest": decision.closed_prefix_digest,
        "authority_source_id": "authority:foreign",
        "earliest_revocation_cut": decision.earliest_revocation_cut,
        "status": decision.status,
        "effect_id": decision.effect_id,
        "reason": decision.reason,
        "raw_event_ids": decision.raw_event_ids,
    }
    foreign = AuthorityDecision(**payload, decision_digest=sha256_digest(payload))
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=trusted
    )
    receipt = monitor.execute(req, authority_decision=foreign)
    assert receipt.status == "REJECTED"
    assert receipt.reason == "AUTHORITY_PREFIX_MISMATCH"
    assert monitor.physical_effects == ()


def test_rejected_or_mismatched_authority_decisions_fail_closed():
    req = request()
    rejected, rejected_snapshot = authority_for(req, authorized=False)
    valid, snapshot = authority_for(req)
    cases = [
        (rejected, rejected_snapshot),
        (replace(valid, request_digest="different"), snapshot),
        (replace(valid, capability_version=2), snapshot),
        (replace(valid, invocation_cut=3), snapshot),
        (replace(valid, effect_id="effect:other"), snapshot),
    ]
    expected_reasons = {
        "AUTHORITY_DECISION_REJECTED",
        "AUTHORITY_DECISION_DIGEST_INVALID",
        "AUTHORITY_DECISION_BINDING_MISMATCH",
    }
    for decision, trusted in cases:
        monitor = ReferenceMonitor(
            {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=trusted
        )
        receipt = monitor.execute(req, authority_decision=decision)
        assert receipt.status == "REJECTED"
        assert receipt.reason in expected_reasons
        assert monitor.physical_effects == ()


def test_rejected_request_id_is_bound_to_first_digest():
    good_changed = request(scope="actuate")
    _, snapshot = authority_for(good_changed)
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=snapshot
    )
    bad = request(scope="observe_passive")
    first = monitor.execute(bad)
    assert first.status == "REJECTED"
    assert monitor.execute(bad) == first
    second = monitor.execute(good_changed)
    assert second.status == "REQUEST_ID_MISMATCH"
    assert monitor.physical_effects == ()
    assert len(monitor.audit) == 1


def test_successful_request_id_is_bound_to_first_digest():
    req = request()
    decision, snapshot = authority_for(req)
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=snapshot
    )
    first = monitor.execute(req, authority_decision=decision)
    changed = request(command="DESTRUCTIVE_READ", scope="measure_active", instrument="instrument:active")
    second = monitor.execute(changed)
    assert first.status == "APPLIED"
    assert second.status == "REQUEST_ID_MISMATCH"
    assert monitor.physical_effects == ("effect:r",)


def test_nonce_replay_under_different_request_is_rejected():
    first = request(request_id="r1", nonce="same")
    second = request(request_id="r2", nonce="same")
    decisions, snapshot = authority_bundle(first, second)
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=snapshot
    )
    assert monitor.execute(first, authority_decision=decisions["r1"]).status == "APPLIED"
    rejected = monitor.execute(second, authority_decision=decisions["r2"])
    assert rejected.status == "REJECTED"
    assert rejected.reason == "NONCE_REPLAY"
    assert monitor.physical_effects == ("effect:r1",)


def test_in_memory_same_nonce_concurrency_creates_one_effect():
    requests = tuple(request(request_id=f"r{i}", nonce="shared") for i in range(32))
    decisions, snapshot = authority_bundle(*requests)
    monitor = ReferenceMonitor(
        {"cap": capability()}, default_registry(), server_cut=2, server_time=2, trusted_prefix=snapshot
    )

    def worker(req: ControlRequest):
        return monitor.execute(req, authority_decision=decisions[req.context.request_id]).status

    with ThreadPoolExecutor(max_workers=16) as pool:
        statuses = list(pool.map(worker, requests))
    assert statuses.count("APPLIED") == 1
    assert statuses.count("REJECTED") == 31
    assert len(monitor.physical_effects) == 1
    assert len(monitor.used_nonces) == 1


def test_capability_and_operation_validation():
    trusted = empty_prefix(2)
    cases = [
        (capability(), request(cut=3), "STALE_OR_FUTURE_CUT"),
        (replace(capability(), active=False), request(), "CAPABILITY_INACTIVE"),
        (replace(capability(), principal="other"), request(), "PRINCIPAL_MISMATCH"),
        (replace(capability(), version=2), request(), "CAPABILITY_VERSION_MISMATCH"),
        (replace(capability(), scopes=frozenset({"observe_passive"})), request(), "SCOPE_NOT_GRANTED"),
        (replace(capability(), expiry_time=1), request(), "CAPABILITY_EXPIRED"),
    ]
    for cap, req, reason in cases:
        monitor = ReferenceMonitor(
            {"cap": cap}, default_registry(), server_cut=2, server_time=2, trusted_prefix=trusted
        )
        receipt = monitor.execute(req)
        assert receipt.status == "REJECTED"
        assert receipt.reason == reason
        assert monitor.physical_effects == ()


def sqlite_store(tmp_path: Path, trusted_prefix: AuthorityPrefixSnapshot):
    store = SQLiteReferenceMonitor(tmp_path / "monitor.sqlite3", default_registry())
    store.initialize([capability()], server_cut=2, server_time=2, trusted_prefix=trusted_prefix)
    return store


def test_sqlite_matching_authority_and_exact_retry(tmp_path):
    req = request()
    decision, snapshot = authority_for(req)
    store = sqlite_store(tmp_path, snapshot)
    first = store.execute(req, authority_decision=decision)
    second = store.execute(req, authority_decision=decision)
    assert first == second
    assert first.authority_prefix_digest == snapshot.closed_prefix_digest
    assert store.counts() == {"requests": 1, "nonces": 1, "effects": 1, "audit": 1}


def test_sqlite_foreign_prefix_rejected_without_effect(tmp_path):
    req = request()
    decision, trusted = authority_for(req)
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
    store = sqlite_store(tmp_path, trusted)
    receipt = store.execute(req, authority_decision=foreign)
    assert receipt.status == "REJECTED"
    assert receipt.reason == "AUTHORITY_PREFIX_MISMATCH"
    assert store.counts()["effects"] == 0


def test_sqlite_tampered_trusted_prefix_meta_is_detected(tmp_path):
    req = request()
    decision, trusted = authority_for(req)
    store = sqlite_store(tmp_path, trusted)
    conn = sqlite3.connect(store.path)
    conn.execute("UPDATE meta SET value='foreign-prefix' WHERE key='closed_prefix_digest'")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="snapshot digest mismatch"):
        store.execute(req, authority_decision=decision)
    assert store.counts()["effects"] == 0


def test_sqlite_rejected_request_binding(tmp_path):
    changed = request(scope="actuate")
    _, snapshot = authority_for(changed)
    store = sqlite_store(tmp_path, snapshot)
    bad = request(scope="observe_passive")
    first = store.execute(bad)
    second = store.execute(changed)
    assert first.status == "REJECTED"
    assert second.status == "REQUEST_ID_MISMATCH"
    assert store.counts()["effects"] == 0


def test_sqlite_no_authority_no_effect(tmp_path):
    req = request()
    _, snapshot = authority_for(req)
    store = sqlite_store(tmp_path, snapshot)
    receipt = store.execute(req)
    assert receipt.reason == "AUTHORITY_DECISION_MISSING"
    assert store.counts()["effects"] == 0


def test_sqlite_same_nonce_thread_concurrency(tmp_path):
    requests = tuple(request(request_id=f"r{i}", nonce="shared") for i in range(24))
    decisions, snapshot = authority_bundle(*requests)
    store = sqlite_store(tmp_path, snapshot)

    def worker(req: ControlRequest):
        return store.execute(req, authority_decision=decisions[req.context.request_id]).status

    with ThreadPoolExecutor(max_workers=12) as pool:
        statuses = list(pool.map(worker, requests))
    assert statuses.count("APPLIED") == 1
    assert statuses.count("REJECTED") == 23
    counts = store.counts()
    assert counts["effects"] == 1
    assert counts["nonces"] == 1
    assert counts["requests"] == 24


def test_sqlite_stored_receipt_tampering_detected(tmp_path):
    req = request()
    decision, snapshot = authority_for(req)
    store = sqlite_store(tmp_path, snapshot)
    store.execute(req, authority_decision=decision)
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
