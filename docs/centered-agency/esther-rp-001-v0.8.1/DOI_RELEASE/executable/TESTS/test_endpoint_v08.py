from __future__ import annotations

from dataclasses import replace

import pytest

from common_v08 import ObligationStatus, ResponseStatus
from endpoint_v08 import (
    AssignmentManifest,
    AssignmentRegistry,
    DEFAULT_SCORING_CONFIG,
    EpisodeLoss,
    ObligationResponse,
    OpportunitySpec,
    RecoveryResponse,
    RetrospectiveResponse,
    ScoringConfig,
    run_endpoint_checks,
    score_oca,
    score_par,
    score_rcs,
    score_srr,
)


def assignment(endpoint="SRR", *, aid="a", block="b", arm="T", unresolved=()):
    opportunities = tuple(
        OpportunitySpec(oid, endpoint, oid in set(unresolved))
        for oid in sorted(("easy", "hard"))
    )
    return AssignmentManifest(aid, block, arm, "task-v1", opportunities, DEFAULT_SCORING_CONFIG.digest)


def test_assignment_digest_is_stable():
    a = assignment()
    assert a.digest == assignment().digest


@pytest.mark.parametrize(
    "change",
    [
        {"block_id": "other"},
        {"arm": "C"},
        {"task_version": "task-v2"},
        {"opportunities": (OpportunitySpec("easy", "SRR"),)},
        {"opportunities": (OpportunitySpec("easy", "SRR", True), OpportunitySpec("hard", "SRR"))},
        {"scoring_config_digest": "other"},
    ],
)
def test_assignment_registry_rejects_same_id_changed_content(change):
    original = assignment()
    registry = AssignmentRegistry((original,))
    altered = replace(original, **change)
    with pytest.raises(ValueError):
        registry.verify(altered)


def test_assignment_registry_rejects_changed_content_on_register():
    original = assignment()
    registry = AssignmentRegistry((original,))
    with pytest.raises(ValueError, match="different content"):
        registry.register(replace(original, arm="C"))


def test_assignment_requires_sorted_unique_opportunities():
    with pytest.raises(ValueError, match="sorted"):
        AssignmentManifest(
            "a", "b", "T", "task", (OpportunitySpec("z", "SRR"), OpportunitySpec("a", "SRR")), DEFAULT_SCORING_CONFIG.digest
        ).validate()
    with pytest.raises(ValueError, match="unique"):
        AssignmentManifest(
            "a", "b", "T", "task", (OpportunitySpec("a", "SRR"), OpportunitySpec("a", "SRR")), DEFAULT_SCORING_CONFIG.digest
        ).validate()


def test_srr_fixed_denominator_penalizes_omission():
    a = assignment()
    registry = AssignmentRegistry((a,))
    result = score_srr(
        a,
        registry,
        (
            RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
            RetrospectiveResponse("a", "hard", ResponseStatus.OMITTED, None),
        ),
    )
    assert result.denominator == 2
    assert result.numerator == 1
    assert result.score == 0.5


def test_srr_predeclared_genuinely_unresolvable_can_be_unresolved_without_penalty():
    a = assignment(unresolved=("hard",))
    registry = AssignmentRegistry((a,))
    result = score_srr(
        a,
        registry,
        (
            RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
            RetrospectiveResponse("a", "hard", ResponseStatus.UNRESOLVED, None),
        ),
    )
    assert result.score == 0


def test_srr_unresolved_not_predeclared_is_penalized():
    a = assignment()
    registry = AssignmentRegistry((a,))
    result = score_srr(
        a,
        registry,
        (
            RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
            RetrospectiveResponse("a", "hard", ResponseStatus.UNRESOLVED, None),
        ),
    )
    assert result.score == 0.5


@pytest.mark.parametrize(
    "rows,error",
    [
        ((RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),), "match sealed"),
        (
            (
                RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
                RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
            ),
            "duplicate",
        ),
        (
            (
                RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
                RetrospectiveResponse("other", "hard", ResponseStatus.ANSWERED, False),
            ),
            "cross-assignment",
        ),
        (
            (
                RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
                RetrospectiveResponse("a", "extra", ResponseStatus.ANSWERED, False),
            ),
            "match sealed",
        ),
    ],
)
def test_scorer_rejects_missing_duplicate_extra_or_cross_assignment(rows, error):
    a = assignment()
    registry = AssignmentRegistry((a,))
    with pytest.raises(ValueError, match=error):
        score_srr(a, registry, rows)


def test_answered_srr_requires_adjudication():
    a = assignment()
    registry = AssignmentRegistry((a,))
    with pytest.raises(ValueError, match="adjudication"):
        score_srr(
            a,
            registry,
            (
                RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, None),
                RetrospectiveResponse("a", "hard", ResponseStatus.ANSWERED, False),
            ),
        )


def test_oca_requires_status_and_lineage():
    a = assignment("OCA")
    registry = AssignmentRegistry((a,))
    result = score_oca(
        a,
        registry,
        (
            ObligationResponse("a", "easy", ResponseStatus.ANSWERED, ObligationStatus.ACTIVE, ObligationStatus.ACTIVE, True),
            ObligationResponse("a", "hard", ResponseStatus.ANSWERED, ObligationStatus.SATISFIED, ObligationStatus.SATISFIED, False),
        ),
    )
    assert result.score == 0.5


def test_par_uses_frozen_weights_and_lineage():
    a = assignment("PAR")
    registry = AssignmentRegistry((a,))
    result = score_par(
        a,
        registry,
        (
            RecoveryResponse("a", "easy", ResponseStatus.ANSWERED, "observed", "observed", frozenset({"x"}), frozenset({"x"})),
            RecoveryResponse("a", "hard", ResponseStatus.ANSWERED, "reconstructed", "unknown", frozenset({"a", "b"}), frozenset({"a"})),
        ),
    )
    assert result.denominator == 2
    assert result.score == pytest.approx((1.0 + 0.4 * 0.5) / 2)


def test_scoring_config_is_sealed_and_validated():
    bad = ScoringConfig(par_label_weight=0.7, par_lineage_weight=0.4)
    with pytest.raises(ValueError, match="sum"):
        bad.validate()
    a = assignment()
    registry = AssignmentRegistry((a,))
    other = ScoringConfig(config_id="other")
    with pytest.raises(ValueError, match="config mismatch"):
        score_srr(
            a,
            registry,
            (
                RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
                RetrospectiveResponse("a", "hard", ResponseStatus.ANSWERED, False),
            ),
            config=other,
        )


def test_rcs_uses_itt_failure_loss():
    a = assignment("RCS")
    registry = AssignmentRegistry((a,))
    answered = score_rcs(a, registry, EpisodeLoss("a", "b", "T", 0.8, 0.2))
    timeout = score_rcs(a, registry, EpisodeLoss("a", "b", "T", 0.8, None, ResponseStatus.TIMEOUT))
    assert answered.rcs == pytest.approx(0.6)
    assert timeout.rcs == pytest.approx(-0.2)


def test_rcs_identity_and_loss_ranges_are_validated():
    a = assignment("RCS")
    registry = AssignmentRegistry((a,))
    with pytest.raises(ValueError, match="identity"):
        score_rcs(a, registry, EpisodeLoss("other", "b", "T", 0.8, 0.2))
    with pytest.raises(ValueError, match="within"):
        score_rcs(a, registry, EpisodeLoss("a", "b", "T", 2.0, 0.2))


def test_aggregate_endpoint_checks_pass():
    assert run_endpoint_checks()["pass"]
