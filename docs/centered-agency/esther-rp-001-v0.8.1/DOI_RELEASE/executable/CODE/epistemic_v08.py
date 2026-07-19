from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping, Sequence

from common_v08 import DecisionKind, EvidenceStatus, require_nonempty_text, sha256_digest


class BridgeProfile(str, Enum):
    CLASSICAL_CONSISTENT = "CLASSICAL_CONSISTENT"
    PARACONSISTENT = "PARACONSISTENT"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    claim: str
    source: str
    reliability: Decimal
    status: EvidenceStatus
    content: str = ""

    @property
    def content_digest(self) -> str:
        return sha256_digest(
            {
                "claim": self.claim,
                "source": self.source,
                "reliability": self.reliability,
                "content": self.content,
            }
        )

    def validate(self) -> None:
        require_nonempty_text(self.evidence_id, "evidence_id")
        require_nonempty_text(self.claim, "claim")
        require_nonempty_text(self.source, "source")
        if not isinstance(self.status, EvidenceStatus):
            raise ValueError("status must be EvidenceStatus")
        if not Decimal("0") <= self.reliability <= Decimal("1"):
            raise ValueError("reliability must be within [0,1]")


@dataclass(frozen=True)
class EvidenceTransition:
    evidence_id: str
    old_status: EvidenceStatus | None
    new_status: EvidenceStatus
    actor: str
    reason: str
    transition_digest: str


_ALLOWED_TRANSITIONS: Mapping[EvidenceStatus, frozenset[EvidenceStatus]] = {
    EvidenceStatus.ACCEPTED: frozenset({EvidenceStatus.CONTESTED, EvidenceStatus.QUARANTINED, EvidenceStatus.REJECTED}),
    EvidenceStatus.PROVISIONAL: frozenset({EvidenceStatus.ACCEPTED, EvidenceStatus.CONTESTED, EvidenceStatus.QUARANTINED, EvidenceStatus.REJECTED}),
    EvidenceStatus.CONTESTED: frozenset({EvidenceStatus.ACCEPTED, EvidenceStatus.QUARANTINED, EvidenceStatus.REJECTED}),
    EvidenceStatus.QUARANTINED: frozenset({EvidenceStatus.PROVISIONAL, EvidenceStatus.CONTESTED, EvidenceStatus.REJECTED}),
    EvidenceStatus.REJECTED: frozenset({EvidenceStatus.PROVISIONAL, EvidenceStatus.QUARANTINED}),
}


@dataclass(frozen=True)
class EpistemicState:
    evidence_registry: tuple[tuple[str, Evidence], ...] = ()
    transitions: tuple[EvidenceTransition, ...] = ()
    bridge_profile: BridgeProfile = BridgeProfile.CLASSICAL_CONSISTENT
    credal_bounds: tuple[tuple[str, Decimal, Decimal], ...] = ()

    def evidence_map(self) -> dict[str, Evidence]:
        return dict(self.evidence_registry)

    def status_map(self) -> dict[str, EvidenceStatus]:
        return {eid: evidence.status for eid, evidence in self.evidence_registry}

    def claim_status(self, claim: str) -> EvidenceStatus | None:
        statuses = [ev.status for _, ev in self.evidence_registry if ev.claim == claim]
        if not statuses:
            return None
        unique = set(statuses)
        if EvidenceStatus.CONTESTED in unique or (
            EvidenceStatus.ACCEPTED in unique and EvidenceStatus.REJECTED in unique
        ):
            return EvidenceStatus.CONTESTED
        if EvidenceStatus.ACCEPTED in unique:
            return EvidenceStatus.ACCEPTED
        if EvidenceStatus.PROVISIONAL in unique:
            return EvidenceStatus.PROVISIONAL
        if EvidenceStatus.QUARANTINED in unique:
            return EvidenceStatus.QUARANTINED
        return EvidenceStatus.REJECTED

    def claims_by_current_status(self) -> dict[EvidenceStatus, frozenset[str]]:
        claims = {ev.claim for _, ev in self.evidence_registry}
        out: dict[EvidenceStatus, set[str]] = {s: set() for s in EvidenceStatus}
        for claim in claims:
            status = self.claim_status(claim)
            if status is not None:
                out[status].add(claim)
        return {status: frozenset(values) for status, values in out.items()}

    @property
    def accepted_beliefs(self) -> frozenset[str]:
        return self.claims_by_current_status()[EvidenceStatus.ACCEPTED]

    @property
    def provisional_beliefs(self) -> frozenset[str]:
        return self.claims_by_current_status()[EvidenceStatus.PROVISIONAL]

    @property
    def contested_beliefs(self) -> frozenset[str]:
        return self.claims_by_current_status()[EvidenceStatus.CONTESTED]

    @property
    def quarantined_beliefs(self) -> frozenset[str]:
        return self.claims_by_current_status()[EvidenceStatus.QUARANTINED]

    @property
    def rejected_beliefs(self) -> frozenset[str]:
        return self.claims_by_current_status()[EvidenceStatus.REJECTED]


def _validate_state(state: EpistemicState) -> None:
    if not isinstance(state.bridge_profile, BridgeProfile):
        raise ValueError("bridge_profile must be BridgeProfile")
    ids = [eid for eid, _ in state.evidence_registry]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate evidence IDs in registry")
    for eid, evidence in state.evidence_registry:
        if eid != evidence.evidence_id:
            raise ValueError("registry key/evidence identity mismatch")
        evidence.validate()
    aliases: dict[str, tuple[Decimal, Decimal]] = {}
    for claim, lower, upper in state.credal_bounds:
        canonical = claim.strip().casefold()
        if canonical in aliases:
            raise ValueError("duplicate credal alias")
        if not Decimal("0") <= lower <= upper <= Decimal("1"):
            raise ValueError("credal bounds must satisfy 0 <= lower <= upper <= 1")
        aliases[canonical] = (lower, upper)


def register_evidence(state: EpistemicState, evidence: Evidence, *, actor: str, reason: str) -> EpistemicState:
    _validate_state(state)
    evidence.validate()
    require_nonempty_text(actor, "actor")
    require_nonempty_text(reason, "reason")
    registry = state.evidence_map()
    if evidence.evidence_id in registry:
        prior = registry[evidence.evidence_id]
        if prior.content_digest != evidence.content_digest:
            raise ValueError("evidence ID is already bound to different content")
        if prior.status != evidence.status:
            raise ValueError("status changes require transition_evidence")
        return state
    registry[evidence.evidence_id] = evidence
    payload = {
        "evidence_id": evidence.evidence_id,
        "old_status": None,
        "new_status": evidence.status.value,
        "actor": actor,
        "reason": reason,
        "content_digest": evidence.content_digest,
    }
    transition = EvidenceTransition(
        evidence_id=evidence.evidence_id,
        old_status=None,
        new_status=evidence.status,
        actor=actor,
        reason=reason,
        transition_digest=sha256_digest(payload),
    )
    return replace(state, evidence_registry=tuple(sorted(registry.items())), transitions=state.transitions + (transition,))


def transition_evidence(
    state: EpistemicState,
    evidence_id: str,
    new_status: EvidenceStatus,
    *,
    actor: str,
    reason: str,
) -> EpistemicState:
    _validate_state(state)
    require_nonempty_text(actor, "actor")
    require_nonempty_text(reason, "reason")
    if not isinstance(new_status, EvidenceStatus):
        raise ValueError("new_status must be EvidenceStatus")
    registry = state.evidence_map()
    prior = registry[evidence_id]
    if prior.status == new_status:
        return state
    if new_status not in _ALLOWED_TRANSITIONS[prior.status]:
        raise ValueError(f"transition {prior.status.value}->{new_status.value} is not allowed")
    updated = replace(prior, status=new_status)
    registry[evidence_id] = updated
    payload = {
        "evidence_id": evidence_id,
        "old_status": prior.status.value,
        "new_status": new_status.value,
        "actor": actor,
        "reason": reason,
        "content_digest": prior.content_digest,
    }
    transition = EvidenceTransition(
        evidence_id=evidence_id,
        old_status=prior.status,
        new_status=new_status,
        actor=actor,
        reason=reason,
        transition_digest=sha256_digest(payload),
    )
    return replace(state, evidence_registry=tuple(sorted(registry.items())), transitions=state.transitions + (transition,))


def revise(state: EpistemicState, evidence: Evidence) -> EpistemicState:
    """Compatibility helper: register once; never silently promotes status."""
    return register_evidence(state, evidence, actor="revision-engine", reason="evidence registration")


@dataclass(frozen=True)
class ModelRisk:
    model_id: str
    losses: tuple[tuple[str, Decimal], ...]

    def loss_map(self) -> dict[str, Decimal]:
        require_nonempty_text(self.model_id, "model_id")
        out: dict[str, Decimal] = {}
        for action, loss in self.losses:
            require_nonempty_text(action, "action")
            if action in out:
                raise ValueError("duplicate action in model loss table")
            if not loss.is_finite():
                raise ValueError("loss must be finite")
            out[action] = loss
        return out


@dataclass(frozen=True)
class PriorEVI:
    prior_id: str
    baseline_losses: tuple[tuple[str, Decimal], ...]
    signal_probabilities: tuple[tuple[str, Decimal], ...]
    post_signal_losses: tuple[tuple[str, tuple[tuple[str, Decimal], ...]], ...]

    def validate(self, action_universe: frozenset[str]) -> None:
        require_nonempty_text(self.prior_id, "prior_id")
        baseline = dict(self.baseline_losses)
        if set(baseline) != set(action_universe):
            raise ValueError("baseline loss table must use exact action universe")
        signals = dict(self.signal_probabilities)
        if len(signals) != len(self.signal_probabilities) or not signals:
            raise ValueError("signal IDs must be unique and nonempty")
        if any((not p.is_finite()) or p < 0 or p > 1 for p in signals.values()):
            raise ValueError("signal probabilities must be finite within [0,1]")
        if sum(signals.values(), Decimal("0")) != Decimal("1"):
            raise ValueError("signal probabilities must sum exactly to one")
        post = dict(self.post_signal_losses)
        if set(post) != set(signals):
            raise ValueError("post-signal loss tables must match signal IDs")
        for signal, table in post.items():
            values = dict(table)
            if set(values) != set(action_universe):
                raise ValueError(f"post-signal table {signal} must use exact action universe")
            if any(not loss.is_finite() for loss in values.values()):
                raise ValueError("post-signal losses must be finite")
        if any(not loss.is_finite() for loss in baseline.values()):
            raise ValueError("baseline losses must be finite")


@dataclass(frozen=True)
class ActionOption:
    action_id: str
    kind: DecisionKind

    def validate(self) -> None:
        require_nonempty_text(self.action_id, "action_id")
        if not isinstance(self.kind, DecisionKind):
            raise ValueError("kind must be DecisionKind")


@dataclass(frozen=True)
class SOCDecision:
    decision: str | None
    decision_kind: DecisionKind | None
    reason: str
    safe_actions: tuple[str, ...]
    relevant_models: tuple[str, ...]
    evi: Decimal
    action_universe_digest: str


def _validate_soc_inputs(actions: Sequence[ActionOption], models: Sequence[ModelRisk], priors: Sequence[PriorEVI]) -> tuple[tuple[str, ...], dict[str, DecisionKind], dict[str, dict[str, Decimal]]]:
    if not actions:
        raise ValueError("action universe cannot be empty")
    for action in actions:
        action.validate()
    action_ids = tuple(a.action_id for a in actions)
    if len(action_ids) != len(set(action_ids)):
        raise ValueError("action IDs must be unique")
    kind_map = {a.action_id: a.kind for a in actions}

    if not models:
        raise ValueError("at least one admitted model is required")
    model_ids = [m.model_id for m in models]
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("model IDs must be unique")
    action_set = frozenset(action_ids)
    model_maps: dict[str, dict[str, Decimal]] = {}
    for model in models:
        losses = model.loss_map()
        if set(losses) != set(action_set):
            raise ValueError("every model must evaluate the exact action universe")
        model_maps[model.model_id] = losses

    prior_ids = [p.prior_id for p in priors]
    if len(prior_ids) != len(set(prior_ids)):
        raise ValueError("prior IDs must be unique")
    for prior in priors:
        prior.validate(action_set)
    return action_ids, kind_map, model_maps


def robust_lower_evi(priors: Sequence[PriorEVI], action_universe: Sequence[str]) -> Decimal:
    action_set = frozenset(action_universe)
    if not priors:
        return Decimal("0")
    values: list[Decimal] = []
    for prior in priors:
        prior.validate(action_set)
        baseline = dict(prior.baseline_losses)
        baseline_value = min(baseline.values())
        probs = dict(prior.signal_probabilities)
        post = dict(prior.post_signal_losses)
        post_value = Decimal("0")
        for signal, probability in probs.items():
            post_value += probability * min(dict(post[signal]).values())
        values.append(baseline_value - post_value)
    return min(values)


def decide_soc(
    *,
    actions: Sequence[ActionOption],
    models: Sequence[ModelRisk],
    priors: Sequence[PriorEVI] = (),
    hard_loss_limit: Decimal,
    information_cost: Decimal = Decimal("0"),
    delay_cost: Decimal = Decimal("0"),
    deadline_remaining: int = 0,
    information_action_id: str | None = None,
    escalation_action_id: str | None = None,
    relevance_threshold: Decimal | None = None,
) -> SOCDecision:
    if not hard_loss_limit.is_finite() or hard_loss_limit < 0:
        raise ValueError("hard_loss_limit must be finite and nonnegative")
    if any(not x.is_finite() or x < 0 for x in (information_cost, delay_cost)):
        raise ValueError("costs must be finite and nonnegative")
    if deadline_remaining < 0:
        raise ValueError("deadline_remaining must be nonnegative")

    action_ids, kind_map, model_maps = _validate_soc_inputs(actions, models, priors)
    action_set = frozenset(action_ids)
    if information_action_id is not None:
        if information_action_id not in action_set or kind_map[information_action_id] is not DecisionKind.ACQUIRE_INFORMATION:
            raise ValueError("information action must be a typed member of the frozen action universe")
    if escalation_action_id is not None:
        if escalation_action_id not in action_set or kind_map[escalation_action_id] is not DecisionKind.ESCALATE:
            raise ValueError("escalation action must be a typed member of the frozen action universe")

    safe_actions = tuple(
        sorted(
            action
            for action in action_ids
            if all(losses[action] <= hard_loss_limit for losses in model_maps.values())
        )
    )
    if relevance_threshold is None:
        relevant_models = tuple(sorted(model_maps))
    else:
        relevant_models = tuple(
            sorted(
                mid
                for mid, losses in model_maps.items()
                if max(losses.values()) - min(losses.values()) >= relevance_threshold
            )
        )
    evi = robust_lower_evi(priors, action_ids)
    universe_digest = sha256_digest(
        {
            "actions": [(a.action_id, a.kind.value) for a in actions],
            "models": [(m.model_id, m.losses) for m in models],
        }
    )

    if not safe_actions:
        return SOCDecision(None, None, "NO_SAFE_ACTION", (), relevant_models, evi, universe_digest)

    info_threshold = information_cost + delay_cost
    if (
        deadline_remaining > 0
        and information_action_id is not None
        and information_action_id in safe_actions
        and evi > info_threshold
    ):
        return SOCDecision(
            information_action_id,
            DecisionKind.ACQUIRE_INFORMATION,
            "POSITIVE_ROBUST_EVI",
            safe_actions,
            relevant_models,
            evi,
            universe_digest,
        )

    domain_safe = [a for a in safe_actions if kind_map[a] is DecisionKind.DOMAIN]
    if domain_safe:
        # Minimax hard-loss choice over all admitted models, stable by action ID.
        decision = min(domain_safe, key=lambda a: (max(losses[a] for losses in model_maps.values()), a))
        return SOCDecision(decision, DecisionKind.DOMAIN, "ROBUST_DOMAIN_COMMITMENT", safe_actions, relevant_models, evi, universe_digest)

    if escalation_action_id is not None and escalation_action_id in safe_actions:
        return SOCDecision(escalation_action_id, DecisionKind.ESCALATE, "NO_SAFE_DOMAIN_ACTION", safe_actions, relevant_models, evi, universe_digest)

    # Safe governance actions may exist, but the caller did not declare which one may be used.
    return SOCDecision(None, None, "NO_SELECTED_SAFE_TRANSITION", safe_actions, relevant_models, evi, universe_digest)


def run_epistemic_checks() -> dict:
    state = EpistemicState()
    e = Evidence("ev:1", "wall_is_load_bearing", "sensor", Decimal("0.9"), EvidenceStatus.CONTESTED, "reading")
    state = register_evidence(state, e, actor="sensor-gateway", reason="ingest")
    state = transition_evidence(state, "ev:1", EvidenceStatus.QUARANTINED, actor="reviewer", reason="calibration stale")

    actions = (
        ActionOption("STOP", DecisionKind.DOMAIN),
        ActionOption("ACQUIRE_INFO", DecisionKind.ACQUIRE_INFORMATION),
        ActionOption("ESCALATE", DecisionKind.ESCALATE),
    )
    models = (
        ModelRisk("load-bearing", (("STOP", Decimal("0")), ("ACQUIRE_INFO", Decimal("1")), ("ESCALATE", Decimal("2")))),
        ModelRisk("non-load-bearing", (("STOP", Decimal("1")), ("ACQUIRE_INFO", Decimal("1")), ("ESCALATE", Decimal("2")))),
    )
    priors = (
        PriorEVI(
            "p",
            (("STOP", Decimal("2")), ("ACQUIRE_INFO", Decimal("1")), ("ESCALATE", Decimal("3"))),
            (("clear", Decimal("1")),),
            (("clear", (("STOP", Decimal("0")), ("ACQUIRE_INFO", Decimal("1")), ("ESCALATE", Decimal("2")))),),
        ),
    )
    decision = decide_soc(
        actions=actions,
        models=models,
        priors=priors,
        hard_loss_limit=Decimal("3"),
        information_cost=Decimal("0"),
        delay_cost=Decimal("0"),
        deadline_remaining=2,
        information_action_id="ACQUIRE_INFO",
        escalation_action_id="ESCALATE",
    )
    checks = {
        "one_current_status_per_evidence": len(state.status_map()) == 1,
        "claim_aggregation_is_single_status": sum("wall_is_load_bearing" in values for values in state.claims_by_current_status().values()) == 1,
        "soc_decision_inside_action_universe": decision.decision in {a.action_id for a in actions},
        "soc_selected_action_is_hard_safe": decision.decision is None or all(dict(m.losses)[decision.decision] <= Decimal("3") for m in models),
    }
    return {"checks": checks, "decision": decision.__dict__, "pass": all(checks.values())}


if __name__ == "__main__":
    import json

    print(json.dumps(run_epistemic_checks(), ensure_ascii=False, indent=2, default=str))
