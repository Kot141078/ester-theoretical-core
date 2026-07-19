from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from itertools import permutations

import pytest

from common_v07 import DecisionKind, EvidenceStatus
from epistemic_v07 import (
    ActionOption,
    BridgeProfile,
    EpistemicState,
    Evidence,
    ModelRisk,
    PriorEVI,
    decide_soc,
    register_evidence,
    revise,
    robust_lower_evi,
    run_epistemic_checks,
    transition_evidence,
)


def evidence(eid="e", claim="p", source="s", reliability=Decimal("0.9"), status=EvidenceStatus.PROVISIONAL, content="x"):
    return Evidence(eid, claim, source, reliability, status, content)


@pytest.mark.parametrize("status", list(EvidenceStatus))
def test_register_each_status_as_single_current_state(status):
    state = register_evidence(EpistemicState(), evidence(status=status), actor="a", reason="r")
    assert state.status_map() == {"e": status}
    assert sum("p" in values for values in state.claims_by_current_status().values()) == 1
    assert len(state.transitions) == 1


def test_same_evidence_registration_is_idempotent():
    state = register_evidence(EpistemicState(), evidence(), actor="a", reason="r")
    assert register_evidence(state, evidence(), actor="a", reason="r2") == state


@pytest.mark.parametrize(
    "changed",
    [
        {"claim": "q"},
        {"source": "other"},
        {"reliability": Decimal("0.8")},
        {"content": "other"},
    ],
)
def test_evidence_id_cannot_be_rebound(changed):
    original = evidence()
    state = register_evidence(EpistemicState(), original, actor="a", reason="r")
    with pytest.raises(ValueError, match="different content"):
        register_evidence(state, replace(original, **changed), actor="a", reason="changed")


def test_status_change_requires_explicit_transition():
    state = register_evidence(EpistemicState(), evidence(), actor="a", reason="r")
    with pytest.raises(ValueError, match="transition_evidence"):
        register_evidence(state, evidence(status=EvidenceStatus.ACCEPTED), actor="a", reason="promote")


@pytest.mark.parametrize(
    "old,new",
    [
        (EvidenceStatus.PROVISIONAL, EvidenceStatus.ACCEPTED),
        (EvidenceStatus.PROVISIONAL, EvidenceStatus.CONTESTED),
        (EvidenceStatus.ACCEPTED, EvidenceStatus.CONTESTED),
        (EvidenceStatus.CONTESTED, EvidenceStatus.QUARANTINED),
        (EvidenceStatus.QUARANTINED, EvidenceStatus.PROVISIONAL),
        (EvidenceStatus.REJECTED, EvidenceStatus.PROVISIONAL),
    ],
)
def test_allowed_status_transitions_have_one_current_state(old, new):
    state = register_evidence(EpistemicState(), evidence(status=old), actor="a", reason="start")
    state2 = transition_evidence(state, "e", new, actor="reviewer", reason="explicit")
    assert state2.status_map()["e"] is new
    assert len(state2.transitions) == 2
    assert sum("p" in values for values in state2.claims_by_current_status().values()) == 1


@pytest.mark.parametrize(
    "old,new",
    [
        (EvidenceStatus.ACCEPTED, EvidenceStatus.PROVISIONAL),
        (EvidenceStatus.REJECTED, EvidenceStatus.ACCEPTED),
        (EvidenceStatus.QUARANTINED, EvidenceStatus.ACCEPTED),
    ],
)
def test_disallowed_status_transitions_fail_closed(old, new):
    state = register_evidence(EpistemicState(), evidence(status=old), actor="a", reason="start")
    before = state
    with pytest.raises(ValueError, match="not allowed"):
        transition_evidence(state, "e", new, actor="reviewer", reason="bad")
    assert state == before


def test_multiple_evidence_items_have_explicit_claim_aggregation():
    state = register_evidence(EpistemicState(), evidence("e1", status=EvidenceStatus.ACCEPTED), actor="a", reason="r")
    state = register_evidence(state, evidence("e2", status=EvidenceStatus.REJECTED), actor="b", reason="r")
    assert state.claim_status("p") is EvidenceStatus.CONTESTED
    assert state.contested_beliefs == frozenset({"p"})
    assert state.accepted_beliefs == frozenset()


def test_bridge_profile_must_be_enum():
    bad = EpistemicState(bridge_profile="typo")
    with pytest.raises(ValueError):
        register_evidence(bad, evidence(), actor="a", reason="r")


def test_credal_aliases_and_bounds_are_validated():
    bad_alias = EpistemicState(credal_bounds=(("P", Decimal("0"), Decimal("0.5")), ("p", Decimal("0.1"), Decimal("0.6"))))
    with pytest.raises(ValueError, match="alias"):
        register_evidence(bad_alias, evidence(), actor="a", reason="r")
    bad_bounds = EpistemicState(credal_bounds=(("p", Decimal("0.7"), Decimal("0.2")),))
    with pytest.raises(ValueError, match="bounds"):
        register_evidence(bad_bounds, evidence(), actor="a", reason="r")


def test_revise_does_not_silently_promote_contested_evidence():
    state = revise(EpistemicState(), evidence(status=EvidenceStatus.CONTESTED))
    assert state.status_map()["e"] is EvidenceStatus.CONTESTED
    assert state.contested_beliefs == frozenset({"p"})


def actions():
    return (
        ActionOption("STOP", DecisionKind.DOMAIN),
        ActionOption("GO", DecisionKind.DOMAIN),
        ActionOption("INFO", DecisionKind.ACQUIRE_INFORMATION),
        ActionOption("ESC", DecisionKind.ESCALATE),
    )


def models():
    return (
        ModelRisk("m1", (("STOP", Decimal("0")), ("GO", Decimal("20")), ("INFO", Decimal("1")), ("ESC", Decimal("2")))),
        ModelRisk("m2", (("STOP", Decimal("1")), ("GO", Decimal("0")), ("INFO", Decimal("1")), ("ESC", Decimal("2")))),
    )


def priors():
    return (
        PriorEVI(
            "p",
            (("STOP", Decimal("5")), ("GO", Decimal("4")), ("INFO", Decimal("2")), ("ESC", Decimal("3"))),
            (("s1", Decimal("0.5")), ("s2", Decimal("0.5"))),
            (
                ("s1", (("STOP", Decimal("1")), ("GO", Decimal("5")), ("INFO", Decimal("2")), ("ESC", Decimal("3")))),
                ("s2", (("STOP", Decimal("5")), ("GO", Decimal("1")), ("INFO", Decimal("2")), ("ESC", Decimal("3")))),
            ),
        ),
    )


def test_soc_never_returns_action_outside_frozen_universe():
    decision = decide_soc(
        actions=actions(),
        models=models(),
        priors=priors(),
        hard_loss_limit=Decimal("10"),
        information_cost=Decimal("0"),
        delay_cost=Decimal("0"),
        deadline_remaining=2,
        information_action_id="INFO",
        escalation_action_id="ESC",
    )
    assert decision.decision in {a.action_id for a in actions()}


def test_soc_hard_safety_uses_all_admitted_models():
    decision = decide_soc(
        actions=actions(),
        models=models(),
        hard_loss_limit=Decimal("10"),
        deadline_remaining=0,
        information_action_id="INFO",
        escalation_action_id="ESC",
        relevance_threshold=Decimal("1000"),
    )
    assert "GO" not in decision.safe_actions
    assert decision.decision == "STOP"


def test_soc_no_safe_action_returns_none_not_unmodeled_meta_action():
    unsafe = (
        ModelRisk("m", (("STOP", Decimal("9")), ("GO", Decimal("9")), ("INFO", Decimal("9")), ("ESC", Decimal("9")))),
    )
    decision = decide_soc(
        actions=actions(),
        models=unsafe,
        priors=(),
        hard_loss_limit=Decimal("1"),
        deadline_remaining=2,
        information_action_id="INFO",
        escalation_action_id="ESC",
    )
    assert decision.decision is None
    assert decision.reason == "NO_SAFE_ACTION"


def test_positive_evi_selects_typed_safe_information_action():
    safe_models = (
        ModelRisk("m", (("STOP", Decimal("1")), ("GO", Decimal("1")), ("INFO", Decimal("0")), ("ESC", Decimal("1")))),
    )
    p = (
        PriorEVI(
            "p",
            (("STOP", Decimal("10")), ("GO", Decimal("10")), ("INFO", Decimal("9")), ("ESC", Decimal("10"))),
            (("s", Decimal("1")),),
            (("s", (("STOP", Decimal("0")), ("GO", Decimal("1")), ("INFO", Decimal("9")), ("ESC", Decimal("2")))),),
        ),
    )
    decision = decide_soc(
        actions=actions(),
        models=safe_models,
        priors=p,
        hard_loss_limit=Decimal("2"),
        information_cost=Decimal("0"),
        delay_cost=Decimal("0"),
        deadline_remaining=1,
        information_action_id="INFO",
        escalation_action_id="ESC",
    )
    assert decision.decision == "INFO"
    assert decision.decision_kind is DecisionKind.ACQUIRE_INFORMATION


def test_information_action_must_be_typed_member_of_universe():
    with pytest.raises(ValueError, match="typed member"):
        decide_soc(actions=actions(), models=models(), hard_loss_limit=Decimal("10"), information_action_id="MISSING")
    wrong = tuple(replace(a, kind=DecisionKind.DOMAIN) if a.action_id == "INFO" else a for a in actions())
    with pytest.raises(ValueError, match="typed member"):
        decide_soc(actions=wrong, models=models(), hard_loss_limit=Decimal("10"), information_action_id="INFO")


@pytest.mark.parametrize(
    "bad_actions,bad_models,bad_priors,match",
    [
        (
            (ActionOption("A", DecisionKind.DOMAIN), ActionOption("A", DecisionKind.ESCALATE)),
            (ModelRisk("m", (("A", Decimal("0")),)),),
            (),
            "action IDs",
        ),
        (
            (ActionOption("A", DecisionKind.DOMAIN),),
            (ModelRisk("m", (("A", Decimal("0")),)), ModelRisk("m", (("A", Decimal("1")),))),
            (),
            "model IDs",
        ),
        (
            (ActionOption("A", DecisionKind.DOMAIN), ActionOption("B", DecisionKind.DOMAIN)),
            (ModelRisk("m", (("A", Decimal("0")),)),),
            (),
            "exact action universe",
        ),
    ],
)
def test_soc_schema_rejects_duplicate_or_incomplete_inputs(bad_actions, bad_models, bad_priors, match):
    with pytest.raises(ValueError, match=match):
        decide_soc(actions=bad_actions, models=bad_models, priors=bad_priors, hard_loss_limit=Decimal("10"))


@pytest.mark.parametrize(
    "probabilities",
    [
        (("s1", Decimal("2")), ("s2", Decimal("-1"))),
        (("s1", Decimal("0.6")), ("s2", Decimal("0.5"))),
        (("s1", Decimal("NaN")),),
    ],
)
def test_evi_rejects_invalid_probability_simplex(probabilities):
    p = PriorEVI(
        "p",
        (("A", Decimal("1")),),
        probabilities,
        tuple((signal, (("A", Decimal("0")),)) for signal, _ in probabilities),
    )
    with pytest.raises(ValueError):
        robust_lower_evi((p,), ("A",))


def test_soc_is_permutation_invariant_for_valid_inputs():
    results = set()
    for action_order in permutations(actions()):
        for model_order in permutations(models()):
            decision = decide_soc(
                actions=action_order,
                models=model_order,
                priors=priors(),
                hard_loss_limit=Decimal("10"),
                deadline_remaining=0,
                information_action_id="INFO",
                escalation_action_id="ESC",
            )
            results.add((decision.decision, decision.safe_actions, decision.relevant_models))
    assert len(results) == 1


def test_aggregate_epistemic_checks_pass():
    assert run_epistemic_checks()["pass"]
