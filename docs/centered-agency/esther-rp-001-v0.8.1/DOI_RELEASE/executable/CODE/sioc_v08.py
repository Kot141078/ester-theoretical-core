from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from enum import Enum
from threading import RLock
from typing import Mapping

import numpy as np

from common_v08 import require_nonempty_text, require_nonnegative_int, sha256_digest
from formal_v08 import AuthorityDecision, AuthorityPrefixSnapshot


class EffectClass(str, Enum):
    NONE = "NONE"
    PHYSICAL = "PHYSICAL"
    QUANTUM_BACKACTION = "QUANTUM_BACKACTION"


@dataclass(frozen=True)
class OperationDescriptor:
    command: str
    instrument_id: str
    instrument_version: str
    effect_class: EffectClass
    effect_budget: Decimal
    required_scope: str

    def validate(self) -> None:
        require_nonempty_text(self.command, "command")
        require_nonempty_text(self.instrument_id, "instrument_id")
        require_nonempty_text(self.instrument_version, "instrument_version")
        require_nonempty_text(self.required_scope, "required_scope")
        if not isinstance(self.effect_class, EffectClass):
            raise ValueError("effect_class must be EffectClass")
        if not self.effect_budget.is_finite() or self.effect_budget < 0:
            raise ValueError("effect_budget must be finite and nonnegative")
        if self.effect_class is EffectClass.NONE:
            if self.effect_budget != 0:
                raise ValueError("effect-free operation must have zero effect budget")
            if self.required_scope != "observe_passive":
                raise ValueError("effect-free operation must use observe_passive scope")
        else:
            if self.effect_budget <= 0:
                raise ValueError("effectful operation must have positive effect budget")
            if self.required_scope == "observe_passive":
                raise ValueError("effectful operation cannot require passive-only scope")

    @property
    def descriptor_digest(self) -> str:
        self.validate()
        return sha256_digest(asdict(self))


class OperationRegistry:
    def __init__(self, descriptors: tuple[OperationDescriptor, ...]) -> None:
        table: dict[tuple[str, str, str], OperationDescriptor] = {}
        for descriptor in descriptors:
            descriptor.validate()
            key = (descriptor.command, descriptor.instrument_id, descriptor.instrument_version)
            if key in table:
                raise ValueError("duplicate operation descriptor")
            table[key] = descriptor
        if not table:
            raise ValueError("operation registry cannot be empty")
        self._table = table
        self._digest = sha256_digest(tuple(sorted((key, value.descriptor_digest) for key, value in table.items())))

    @property
    def digest(self) -> str:
        return self._digest

    def lookup(self, command: str, instrument_id: str, instrument_version: str) -> OperationDescriptor:
        try:
            return self._table[(command, instrument_id, instrument_version)]
        except KeyError as exc:
            raise RequestRejected("UNKNOWN_OPERATION_OR_INSTRUMENT") from exc


def default_registry() -> OperationRegistry:
    return OperationRegistry(
        (
            OperationDescriptor("READ_PASSIVE", "instrument:passive", "v1", EffectClass.NONE, Decimal("0"), "observe_passive"),
            OperationDescriptor("ACTUATE", "actuator:generic", "v1", EffectClass.PHYSICAL, Decimal("1"), "actuate"),
            OperationDescriptor("DESTRUCTIVE_READ", "instrument:active", "v1", EffectClass.PHYSICAL, Decimal("1"), "measure_active"),
            OperationDescriptor("QUANTUM_MEASUREMENT", "instrument:quantum", "v1", EffectClass.QUANTUM_BACKACTION, Decimal("1"), "measure_quantum"),
        )
    )


@dataclass(frozen=True)
class CapabilityRecord:
    capability_id: str
    version: int
    principal: str
    scopes: frozenset[str]
    active: bool
    expiry_time: int

    def validate(self) -> None:
        require_nonempty_text(self.capability_id, "capability_id")
        require_nonempty_text(self.principal, "principal")
        require_nonnegative_int(self.version, "version")
        require_nonnegative_int(self.expiry_time, "expiry_time")
        if not self.scopes or any(not str(scope).strip() for scope in self.scopes):
            raise ValueError("capability scopes must be nonempty")


@dataclass(frozen=True)
class InvocationContext:
    principal: str
    capability_id: str
    capability_version: int
    declared_scope: str
    nonce: str
    request_id: str
    asserted_cut: int

    def validate(self) -> None:
        for field, value in (
            ("principal", self.principal),
            ("capability_id", self.capability_id),
            ("declared_scope", self.declared_scope),
            ("nonce", self.nonce),
            ("request_id", self.request_id),
        ):
            require_nonempty_text(value, field)
        require_nonnegative_int(self.capability_version, "capability_version")
        require_nonnegative_int(self.asserted_cut, "asserted_cut")


@dataclass(frozen=True)
class ControlRequest:
    context: InvocationContext
    command: str
    target_id: str
    instrument_id: str
    instrument_version: str

    def validate(self) -> None:
        self.context.validate()
        for field, value in (
            ("command", self.command),
            ("target_id", self.target_id),
            ("instrument_id", self.instrument_id),
            ("instrument_version", self.instrument_version),
        ):
            require_nonempty_text(value, field)

    @property
    def request_digest(self) -> str:
        self.validate()
        return sha256_digest(asdict(self))

    @property
    def expected_effect_id(self) -> str:
        return f"effect:{self.context.request_id}"


@dataclass(frozen=True)
class EffectReceipt:
    request_id: str
    request_digest: str
    status: str
    reason: str | None
    descriptor_digest: str | None
    effect_class: str | None
    effect_budget: str | None
    effect_id: str | None
    nonce: str
    authority_decision_digest: str | None
    authority_prefix_digest: str | None
    authority_source_id: str | None
    receipt_digest: str

    @classmethod
    def create(
        cls,
        *,
        request: ControlRequest,
        status: str,
        reason: str | None,
        descriptor: OperationDescriptor | None,
        effect_id: str | None,
        authority_decision_digest: str | None,
        trusted_prefix: AuthorityPrefixSnapshot | None = None,
    ) -> "EffectReceipt":
        payload = {
            "request_id": request.context.request_id,
            "request_digest": request.request_digest,
            "status": status,
            "reason": reason,
            "descriptor_digest": descriptor.descriptor_digest if descriptor else None,
            "effect_class": descriptor.effect_class.value if descriptor else None,
            "effect_budget": str(descriptor.effect_budget) if descriptor else None,
            "effect_id": effect_id,
            "nonce": request.context.nonce,
            "authority_decision_digest": authority_decision_digest,
            "authority_prefix_digest": trusted_prefix.closed_prefix_digest if trusted_prefix else None,
            "authority_source_id": trusted_prefix.authority_source_id if trusted_prefix else None,
        }
        return cls(**payload, receipt_digest=sha256_digest(payload))

    def verify_digest(self) -> bool:
        payload = {
            "request_id": self.request_id,
            "request_digest": self.request_digest,
            "status": self.status,
            "reason": self.reason,
            "descriptor_digest": self.descriptor_digest,
            "effect_class": self.effect_class,
            "effect_budget": self.effect_budget,
            "effect_id": self.effect_id,
            "nonce": self.nonce,
            "authority_decision_digest": self.authority_decision_digest,
            "authority_prefix_digest": self.authority_prefix_digest,
            "authority_source_id": self.authority_source_id,
        }
        return self.receipt_digest == sha256_digest(payload)


class RequestRejected(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def validate_request(
    request: ControlRequest,
    *,
    capabilities: Mapping[str, CapabilityRecord],
    registry: OperationRegistry,
    server_cut: int,
    server_time: int,
) -> tuple[OperationDescriptor, CapabilityRecord]:
    request.validate()
    descriptor = registry.lookup(request.command, request.instrument_id, request.instrument_version)
    capability = capabilities.get(request.context.capability_id)
    if capability is None:
        raise RequestRejected("UNKNOWN_CAPABILITY")
    capability.validate()
    if not capability.active:
        raise RequestRejected("CAPABILITY_INACTIVE")
    if capability.version != request.context.capability_version:
        raise RequestRejected("CAPABILITY_VERSION_MISMATCH")
    if capability.principal != request.context.principal:
        raise RequestRejected("PRINCIPAL_MISMATCH")
    if request.context.declared_scope != descriptor.required_scope:
        raise RequestRejected("DECLARED_SCOPE_MISMATCH")
    if descriptor.required_scope not in capability.scopes:
        raise RequestRejected("SCOPE_NOT_GRANTED")
    if request.context.asserted_cut != server_cut:
        raise RequestRejected("STALE_OR_FUTURE_CUT")
    if server_time > capability.expiry_time:
        raise RequestRejected("CAPABILITY_EXPIRED")
    return descriptor, capability


def verify_authority_binding(
    request: ControlRequest,
    descriptor: OperationDescriptor,
    decision: AuthorityDecision | None,
    trusted_prefix: AuthorityPrefixSnapshot | None,
) -> str | None:
    if descriptor.effect_class is EffectClass.NONE:
        return None
    if trusted_prefix is None:
        raise RequestRejected("AUTHORITY_PREFIX_MISSING")
    trusted_prefix.validate()
    if request.context.asserted_cut != trusted_prefix.closed_cut:
        raise RequestRejected("AUTHORITY_PREFIX_CUT_MISMATCH")
    if decision is None:
        raise RequestRejected("AUTHORITY_DECISION_MISSING")
    if not decision.verify_digest():
        raise RequestRejected("AUTHORITY_DECISION_DIGEST_INVALID")
    expected = {
        "request_id": request.context.request_id,
        "request_digest": request.request_digest,
        "capability_id": request.context.capability_id,
        "capability_version": request.context.capability_version,
        "invocation_cut": request.context.asserted_cut,
        "effect_id": request.expected_effect_id,
        "closed_prefix_digest": trusted_prefix.closed_prefix_digest,
        "authority_source_id": trusted_prefix.authority_source_id,
    }
    actual = {
        "request_id": decision.request_id,
        "request_digest": decision.request_digest,
        "capability_id": decision.capability_id,
        "capability_version": decision.capability_version,
        "invocation_cut": decision.invocation_cut,
        "effect_id": decision.effect_id,
        "closed_prefix_digest": decision.closed_prefix_digest,
        "authority_source_id": decision.authority_source_id,
    }
    if actual != expected:
        if (decision.closed_prefix_digest != trusted_prefix.closed_prefix_digest
                or decision.authority_source_id != trusted_prefix.authority_source_id):
            raise RequestRejected("AUTHORITY_PREFIX_MISMATCH")
        raise RequestRejected("AUTHORITY_DECISION_BINDING_MISMATCH")
    if decision.status != "AUTHORIZED":
        raise RequestRejected("AUTHORITY_DECISION_REJECTED")
    return decision.decision_digest



class ReferenceMonitor:
    def __init__(
        self,
        capabilities: Mapping[str, CapabilityRecord],
        registry: OperationRegistry,
        *,
        server_cut: int,
        server_time: int,
        trusted_prefix: AuthorityPrefixSnapshot | None = None,
    ) -> None:
        self._lock = RLock()
        self.capabilities = dict(capabilities)
        self.registry = registry
        self.server_cut = require_nonnegative_int(server_cut, "server_cut")
        self.server_time = require_nonnegative_int(server_time, "server_time")
        if trusted_prefix is not None:
            trusted_prefix.validate()
            if trusted_prefix.closed_cut != self.server_cut:
                raise ValueError("trusted prefix cut must equal server_cut")
        self.trusted_prefix = trusted_prefix
        self._requests: dict[str, tuple[str, EffectReceipt]] = {}
        self._used_nonces: set[tuple[str, int, str]] = set()
        self._physical_effects: tuple[str, ...] = ()
        self._audit: tuple[str, ...] = ()

    @property
    def physical_effects(self) -> tuple[str, ...]:
        with self._lock:
            return self._physical_effects

    @property
    def used_nonces(self) -> frozenset[tuple[str, int, str]]:
        with self._lock:
            return frozenset(self._used_nonces)

    @property
    def audit(self) -> tuple[str, ...]:
        with self._lock:
            return self._audit

    def _mismatch_receipt(self, request: ControlRequest) -> EffectReceipt:
        return EffectReceipt.create(
            request=request,
            status="REQUEST_ID_MISMATCH",
            reason="REQUEST_ID_ALREADY_BOUND_TO_DIFFERENT_DIGEST",
            descriptor=None,
            effect_id=None,
            authority_decision_digest=None,
            trusted_prefix=self.trusted_prefix,
        )

    def execute(self, request: ControlRequest, *, authority_decision: AuthorityDecision | None = None) -> EffectReceipt:
        digest = request.request_digest
        with self._lock:
            prior = self._requests.get(request.context.request_id)
            if prior is not None:
                prior_digest, prior_receipt = prior
                if prior_digest == digest:
                    return prior_receipt
                return self._mismatch_receipt(request)

            descriptor: OperationDescriptor | None = None
            authority_digest: str | None = None
            try:
                descriptor, _ = validate_request(
                    request,
                    capabilities=self.capabilities,
                    registry=self.registry,
                    server_cut=self.server_cut,
                    server_time=self.server_time,
                )
                authority_digest = verify_authority_binding(request, descriptor, authority_decision, self.trusted_prefix)
                nonce_key = (request.context.capability_id, request.context.capability_version, request.context.nonce)
                if nonce_key in self._used_nonces:
                    raise RequestRejected("NONCE_REPLAY")
            except RequestRejected as exc:
                receipt = EffectReceipt.create(
                    request=request,
                    status="REJECTED",
                    reason=exc.reason,
                    descriptor=descriptor,
                    effect_id=None,
                    authority_decision_digest=authority_digest,
                    trusted_prefix=self.trusted_prefix,
                )
                self._requests[request.context.request_id] = (digest, receipt)
                self._audit += (f"Rejected:{receipt.receipt_digest}",)
                return receipt

            assert descriptor is not None
            effect_id = None if descriptor.effect_class is EffectClass.NONE else request.expected_effect_id
            nonce_key = (request.context.capability_id, request.context.capability_version, request.context.nonce)
            receipt = EffectReceipt.create(
                request=request,
                status="OBSERVED" if descriptor.effect_class is EffectClass.NONE else "APPLIED",
                reason=None,
                descriptor=descriptor,
                effect_id=effect_id,
                authority_decision_digest=authority_digest,
                trusted_prefix=self.trusted_prefix,
            )
            # One in-memory publish point under the same lock.
            self._used_nonces.add(nonce_key)
            if effect_id is not None:
                self._physical_effects += (effect_id,)
            self._requests[request.context.request_id] = (digest, receipt)
            self._audit += (f"Committed:{receipt.receipt_digest}",)
            return receipt


# ---------------------------------------------------------------------------
# Quantum numerical profile
# ---------------------------------------------------------------------------


def validate_density_matrix(rho: np.ndarray, *, atol: float = 1e-9) -> bool:
    if not isinstance(rho, np.ndarray) or rho.ndim != 2 or rho.shape[0] != rho.shape[1]:
        return False
    if not np.all(np.isfinite(rho)):
        return False
    if not np.allclose(rho, rho.conj().T, atol=atol, rtol=0):
        return False
    if not np.isclose(np.trace(rho), 1.0, atol=atol, rtol=0):
        return False
    eigenvalues = np.linalg.eigvalsh(rho)
    return bool(np.min(eigenvalues) >= -atol)


def validate_instrument(kraus_by_outcome: Mapping[str, tuple[np.ndarray, ...]], *, atol: float = 1e-9) -> bool:
    if not kraus_by_outcome:
        return False
    shape: tuple[int, int] | None = None
    total: np.ndarray | None = None
    for outcome, operators in kraus_by_outcome.items():
        if not outcome or not operators:
            return False
        for operator in operators:
            if operator.ndim != 2 or operator.shape[0] != operator.shape[1] or not np.all(np.isfinite(operator)):
                return False
            if shape is None:
                shape = operator.shape
                total = np.zeros(shape, dtype=complex)
            if operator.shape != shape:
                return False
            assert total is not None
            total += operator.conj().T @ operator
    assert total is not None and shape is not None
    return bool(np.allclose(total, np.eye(shape[0]), atol=atol, rtol=0))


@dataclass(frozen=True)
class MeasurementAccounting:
    attempted_trials: int
    recorded_outcomes: tuple[str, ...]
    no_clicks: int = 0
    double_clicks: int = 0
    excluded_trials: int = 0

    def validate(self) -> bool:
        try:
            for field, value in (
                ("attempted_trials", self.attempted_trials),
                ("no_clicks", self.no_clicks),
                ("double_clicks", self.double_clicks),
                ("excluded_trials", self.excluded_trials),
            ):
                require_nonnegative_int(value, field)
        except ValueError:
            return False
        return len(self.recorded_outcomes) + self.no_clicks + self.double_clicks + self.excluded_trials == self.attempted_trials


def run_sioc_checks() -> dict:
    registry = default_registry()
    cap = CapabilityRecord("cap", 1, "agent", frozenset({"observe_passive", "actuate"}), True, 10)
    passive = ControlRequest(InvocationContext("agent", "cap", 1, "observe_passive", "n1", "r1", 2), "READ_PASSIVE", "target", "instrument:passive", "v1")
    monitor = ReferenceMonitor({"cap": cap}, registry, server_cut=2, server_time=2)
    p = monitor.execute(passive)
    checks = {
        "passive_has_no_effect": p.status == "OBSERVED" and p.effect_id is None and not monitor.physical_effects,
        "receipt_digest_valid": p.verify_digest(),
        "instrument_rejects_incomplete": not validate_instrument({"0": (np.array([[1.0, 0.0], [0.0, 0.0]]),)}),
        "accounting_rejects_negative": not MeasurementAccounting(1, ("0", "1"), no_clicks=-1).validate(),
    }
    return {"checks": checks, "pass": all(checks.values())}


if __name__ == "__main__":
    import json

    print(json.dumps(run_sioc_checks(), ensure_ascii=False, indent=2, default=str))
