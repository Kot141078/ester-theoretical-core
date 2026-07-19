from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from analysis_independent_v08 import analyze_raw_fixture
from analysis_v08 import (
    AnalysisPlan,
    AnalysisPlanRegistry,
    BlockEndpoint,
    TailPair,
    analyze_named_estimands,
    block_rcg,
    catastrophic_tail_gate,
    default_plan,
    run_analysis_checks,
)
from endpoint_v08 import DEFAULT_SCORING_CONFIG, EpisodeRCS, PRIMARY_ENDPOINTS


def blocks(n=200):
    return tuple(f"b{i:03d}" for i in range(n))


def fixture_rows(block_ids, mode="equivalent"):
    rows = []
    for idx, block in enumerate(block_ids):
        jitter = ((idx % 5) - 2) * 0.001
        for endpoint in PRIMARY_ENDPOINTS:
            if mode == "equivalent":
                contrast = jitter
            elif mode == "superior":
                contrast = 0.12 + jitter
            elif mode == "one_margin_outside":
                contrast = 0.12 if endpoint == "RCG" else jitter
            elif mode == "reverse_harm":
                contrast = -0.12 + jitter
            else:
                raise ValueError(mode)
            if endpoint == "SRR":
                treatment, control = 0.20 - contrast, 0.20
            else:
                treatment, control = 0.50 + contrast, 0.50
            rows.append(BlockEndpoint(block, endpoint, treatment, control))
    return rows


def raw_plan(plan):
    return {
        "plan_id": plan.plan_id,
        "endpoint_names": list(plan.endpoint_names),
        "expected_block_ids": list(plan.expected_block_ids),
        "margins": dict(plan.margins),
        "family_alpha": plan.family_alpha,
        "catastrophic_margin": plan.catastrophic_margin,
        "scoring_config_digest": plan.scoring_config_digest,
        "tail_method": plan.tail_method,
        "software_profile": list(plan.software_profile),
    }


def raw_rows(rows):
    return [asdict(row) for row in rows]


def raw_tail(rows):
    return [asdict(row) for row in rows]


def compare(rows, plan, registry, tail):
    primary = analyze_named_estimands(rows, plan=plan, registry=registry, tail_pairs=tail)
    secondary = analyze_raw_fixture(raw_rows(rows), raw_plan(plan), raw_tail(tail), expected_plan_digest=plan.digest)
    assert primary.verdict == secondary["verdict"]
    assert primary.superiority == secondary["superiority"]
    assert primary.equivalence == secondary["equivalence"]
    assert primary.tail_gate_pass == secondary["tail_gate_pass"]
    for endpoint in (*PRIMARY_ENDPOINTS, "TAIL"):
        for key, value in primary.endpoint_rows[endpoint].items():
            other = secondary["endpoint_rows"][endpoint][key]
            if isinstance(value, float):
                assert value == pytest.approx(float(other), abs=1e-12)
            else:
                assert value == other
    return primary


def setup_plan(n=200):
    plan = default_plan(blocks(n), DEFAULT_SCORING_CONFIG.digest)
    return plan, AnalysisPlanRegistry((plan,))


def test_plan_registry_accepts_original():
    plan, registry = setup_plan()
    registry.verify(plan)


@pytest.mark.parametrize(
    "change",
    [
        {"expected_block_ids": blocks(199)},
        {"margins": (("SRR", 0.5), ("OCA", 0.05), ("PAR", 0.05), ("RCG", 0.08))},
        {"family_alpha": 0.1},
        {"catastrophic_margin": 0.05},
        {"scoring_config_digest": "other"},
        {"tail_method": "OTHER"},
        {"software_profile": ("other",)},
    ],
)
def test_same_plan_id_changed_content_rejected(change):
    plan, registry = setup_plan()
    altered = replace(plan, **change)
    with pytest.raises(ValueError):
        registry.verify(altered)


def test_plan_registry_rejects_reregistered_changed_content():
    plan, registry = setup_plan()
    with pytest.raises(ValueError, match="different content"):
        registry.register(replace(plan, family_alpha=0.1))


@pytest.mark.parametrize(
    "plan",
    [
        AnalysisPlan("p", ("RCG",), ("b1", "b2"), (("RCG", 0.1),), 0.05, 0.02, DEFAULT_SCORING_CONFIG.digest),
        AnalysisPlan("p", PRIMARY_ENDPOINTS, ("b", "b"), tuple((e, 0.1) for e in PRIMARY_ENDPOINTS), 0.05, 0.02, DEFAULT_SCORING_CONFIG.digest),
        AnalysisPlan("p", PRIMARY_ENDPOINTS, ("b1", "b2"), tuple((e, -0.1) for e in PRIMARY_ENDPOINTS), 0.05, 0.02, DEFAULT_SCORING_CONFIG.digest),
        AnalysisPlan("p", PRIMARY_ENDPOINTS, ("b1", "b2"), tuple((e, 0.1) for e in PRIMARY_ENDPOINTS), 2.0, 0.02, DEFAULT_SCORING_CONFIG.digest),
    ],
)
def test_invalid_plan_contract_rejected(plan):
    with pytest.raises(ValueError):
        plan.validate()


def test_equivalence_cross_implementation():
    plan, registry = setup_plan()
    tail = [TailPair(b, False, False) for b in plan.expected_block_ids]
    result = compare(fixture_rows(plan.expected_block_ids, "equivalent"), plan, registry, tail)
    assert result.verdict == "JOINT_EQUIVALENCE_ON_NAMED_ESTIMANDS"


def test_superiority_cross_implementation():
    plan, registry = setup_plan()
    tail = [TailPair(b, False, False) for b in plan.expected_block_ids]
    result = compare(fixture_rows(plan.expected_block_ids, "superior"), plan, registry, tail)
    assert result.verdict == "JOINT_SUPERIORITY"


def test_one_margin_outside_fails_equivalence():
    plan, registry = setup_plan()
    tail = [TailPair(b, False, False) for b in plan.expected_block_ids]
    result = compare(fixture_rows(plan.expected_block_ids, "one_margin_outside"), plan, registry, tail)
    assert result.verdict == "INCONCLUSIVE_OR_NON_EQUIVALENT"
    assert not result.endpoint_rows["RCG"]["equivalent"]


def test_reverse_harm_fails_superiority():
    plan, registry = setup_plan()
    tail = [TailPair(b, False, False) for b in plan.expected_block_ids]
    result = compare(fixture_rows(plan.expected_block_ids, "reverse_harm"), plan, registry, tail)
    assert not result.superiority


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "disjoint", "tail_missing", "tail_duplicate"])
def test_universe_integrity_hard_fails(mutation):
    plan, registry = setup_plan(20)
    rows = fixture_rows(plan.expected_block_ids)
    tail = [TailPair(b, False, False) for b in plan.expected_block_ids]
    if mutation == "missing":
        rows = [r for r in rows if not (r.block_id == "b000" and r.endpoint == "PAR")]
    elif mutation == "duplicate":
        rows.append(rows[0])
    elif mutation == "disjoint":
        rows = [r for r in rows if not (r.block_id == "b000" and r.endpoint == "PAR")]
        rows.append(BlockEndpoint("other", "PAR", 0.5, 0.5))
    elif mutation == "tail_missing":
        tail = tail[:-1]
    else:
        tail = tail[:-1] + [tail[0]]
    with pytest.raises(ValueError):
        analyze_named_estimands(rows, plan=plan, registry=registry, tail_pairs=tail)


@pytest.mark.parametrize(
    "endpoint,treatment,control",
    [
        ("SRR", float("nan"), 0.2),
        ("SRR", -0.1, 0.2),
        ("OCA", 1.1, 0.5),
        ("RCG", 2.0, 0.0),
    ],
)
def test_primary_rejects_invalid_endpoint_values(endpoint, treatment, control):
    with pytest.raises(ValueError):
        BlockEndpoint("b", endpoint, treatment, control).validate()


@pytest.mark.parametrize(
    "endpoint,treatment,control",
    [
        ("SRR", float("nan"), 0.2),
        ("SRR", -0.1, 0.2),
        ("OCA", 1.1, 0.5),
        ("RCG", 2.0, 0.0),
    ],
)
def test_secondary_rejects_same_invalid_endpoint_grid(endpoint, treatment, control):
    plan, _ = setup_plan(2)
    rows = raw_rows(fixture_rows(plan.expected_block_ids))
    for row in rows:
        if row["block_id"] == "b000" and row["endpoint"] == endpoint:
            row["treatment_value"] = treatment
            row["control_value"] = control
            break
    tail = raw_tail([TailPair(b, False, False) for b in plan.expected_block_ids])
    with pytest.raises(ValueError):
        analyze_raw_fixture(rows, raw_plan(plan), tail, expected_plan_digest=plan.digest)


def test_secondary_requires_external_expected_digest():
    plan, _ = setup_plan(2)
    rows = raw_rows(fixture_rows(plan.expected_block_ids))
    tail = raw_tail([TailPair(b, False, False) for b in plan.expected_block_ids])
    with pytest.raises(ValueError, match="digest mismatch"):
        analyze_raw_fixture(rows, raw_plan(plan), tail, expected_plan_digest="wrong")


def test_small_n_zero_zero_does_not_pass_tail_margin():
    result = catastrophic_tail_gate([TailPair("b", False, False)], expected_block_ids=("b",), margin=0.02, family_alpha=0.05)
    assert not result["pass"]
    assert result["upper_difference"] > 0


def test_large_zero_zero_can_pass_tail_margin():
    block_ids = blocks(300)
    result = catastrophic_tail_gate([TailPair(b, False, False) for b in block_ids], expected_block_ids=block_ids, margin=0.02, family_alpha=0.05)
    assert result["pass"]


def test_tail_excess_blocks_claim():
    plan, registry = setup_plan()
    tail = [TailPair(b, idx < 10, False) for idx, b in enumerate(plan.expected_block_ids)]
    result = compare(fixture_rows(plan.expected_block_ids, "superior"), plan, registry, tail)
    assert not result.tail_gate_pass


def test_block_rcg_requires_complete_unique_pairs():
    with pytest.raises(ValueError):
        block_rcg((EpisodeRCS("a", "b", "T", 0.5),))
    with pytest.raises(ValueError):
        block_rcg((EpisodeRCS("a", "b", "T", 0.5), EpisodeRCS("a2", "b", "T", 0.6), EpisodeRCS("c", "b", "C", 0.1)))
    rows = block_rcg((EpisodeRCS("a", "b", "T", 0.5), EpisodeRCS("c", "b", "C", 0.1)))
    assert rows[0].contrast == pytest.approx(0.4)


def test_aggregate_analysis_checks_pass():
    assert run_analysis_checks(DEFAULT_SCORING_CONFIG.digest)["pass"]
