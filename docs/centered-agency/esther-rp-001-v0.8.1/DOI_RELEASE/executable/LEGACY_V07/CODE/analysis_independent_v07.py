from __future__ import annotations

from math import isfinite, sqrt
from typing import Mapping, Sequence

import numpy as np
from scipy.stats import beta, t

from common_v07 import sha256_digest


PRIMARY_ENDPOINTS = ("SRR", "OCA", "PAR", "RCG")
TAIL_METHOD = "BONFERRONI_CP_RISK_DIFFERENCE_V1"
SOFTWARE_PROFILE = ("analysis-v0.7", "scipy-t-beta")


def _plan_digest(plan: Mapping[str, object]) -> str:
    return sha256_digest(
        {
            "plan_id": plan["plan_id"],
            "endpoint_names": tuple(plan["endpoint_names"]),
            "expected_block_ids": tuple(plan["expected_block_ids"]),
            "margins": tuple((e, float(plan["margins"][e])) for e in PRIMARY_ENDPOINTS),
            "family_alpha": float(plan["family_alpha"]),
            "catastrophic_margin": float(plan["catastrophic_margin"]),
            "scoring_config_digest": plan["scoring_config_digest"],
            "tail_method": plan["tail_method"],
            "software_profile": tuple(plan["software_profile"]),
        }
    )


def _validate_plan(plan: Mapping[str, object], expected_digest: str) -> tuple[tuple[str, ...], dict[str, float]]:
    required = {
        "plan_id",
        "endpoint_names",
        "expected_block_ids",
        "margins",
        "family_alpha",
        "catastrophic_margin",
        "scoring_config_digest",
        "tail_method",
        "software_profile",
    }
    if set(plan) != required:
        raise ValueError("raw plan field set mismatch")
    if tuple(plan["endpoint_names"]) != PRIMARY_ENDPOINTS:
        raise ValueError("raw plan endpoint set/order mismatch")
    blocks = tuple(plan["expected_block_ids"])
    if not blocks or len(blocks) != len(set(blocks)) or blocks != tuple(sorted(blocks)):
        raise ValueError("raw plan blocks must be nonempty, unique and sorted")
    margins = {str(k): float(v) for k, v in dict(plan["margins"]).items()}
    if set(margins) != set(PRIMARY_ENDPOINTS) or any((not isfinite(v)) or v <= 0 for v in margins.values()):
        raise ValueError("raw plan margins invalid")
    alpha = float(plan["family_alpha"])
    catastrophic = float(plan["catastrophic_margin"])
    if not isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("raw plan alpha invalid")
    if not isfinite(catastrophic) or not 0 < catastrophic < 1:
        raise ValueError("raw plan catastrophic margin invalid")
    if plan["tail_method"] != TAIL_METHOD or tuple(plan["software_profile"]) != SOFTWARE_PROFILE:
        raise ValueError("raw plan method/profile mismatch")
    if not isinstance(plan["scoring_config_digest"], str) or not plan["scoring_config_digest"]:
        raise ValueError("raw plan scoring config digest missing")
    if _plan_digest(plan) != expected_digest:
        raise ValueError("raw plan digest mismatch")
    return blocks, margins


def _validate_value(endpoint: str, value: float) -> None:
    if not isfinite(value):
        raise ValueError("endpoint value must be finite")
    if endpoint in {"SRR", "OCA", "PAR"}:
        if not 0 <= value <= 1:
            raise ValueError("bounded endpoint value outside [0,1]")
    elif not -1 <= value <= 1:
        raise ValueError("RCG value outside [-1,1]")


def _contrast(endpoint: str, treatment: float, control: float) -> float:
    _validate_value(endpoint, treatment)
    _validate_value(endpoint, control)
    return control - treatment if endpoint == "SRR" else treatment - control


def _cp_upper(events: int, n: int, alpha: float) -> float:
    if events == n:
        return 1.0
    return float(beta.ppf(1.0 - alpha, events + 1, n - events))


def _cp_lower(events: int, n: int, alpha: float) -> float:
    if events == 0:
        return 0.0
    return float(beta.ppf(alpha, events, n - events + 1))


def analyze_raw_fixture(
    rows: Sequence[Mapping[str, object]],
    plan: Mapping[str, object],
    tail_rows: Sequence[Mapping[str, object]],
    *,
    expected_plan_digest: str,
) -> dict:
    blocks, margins = _validate_plan(plan, expected_plan_digest)
    expected_pairs = {(b, e) for b in blocks for e in PRIMARY_ENDPOINTS}
    observed: dict[tuple[str, str], float] = {}
    for row in rows:
        if set(row) != {"block_id", "endpoint", "treatment_value", "control_value"}:
            raise ValueError("raw endpoint row field set mismatch")
        block = str(row["block_id"])
        endpoint = str(row["endpoint"])
        if endpoint not in PRIMARY_ENDPOINTS:
            raise ValueError("unknown endpoint")
        key = (block, endpoint)
        if key in observed:
            raise ValueError("duplicate raw block/endpoint row")
        observed[key] = _contrast(endpoint, float(row["treatment_value"]), float(row["control_value"]))
    if set(observed) != expected_pairs:
        raise ValueError("raw rows do not match sealed universe")

    alpha = float(plan["family_alpha"])
    alpha_each = alpha / len(PRIMARY_ENDPOINTS)
    endpoint_rows: dict[str, dict[str, float | bool | str]] = {}
    superiority = []
    equivalence = []
    for endpoint in PRIMARY_ENDPOINTS:
        values = np.asarray([observed[(b, endpoint)] for b in blocks], dtype=float)
        if len(values) < 2 or not np.all(np.isfinite(values)):
            raise ValueError("invalid contrast vector")
        estimate = float(np.mean(values))
        se = float(np.std(values, ddof=1) / sqrt(len(values)))
        critical = float(t.ppf(1.0 - alpha_each / 2.0, len(values) - 1))
        lower = estimate - critical * se
        upper = estimate + critical * se
        superior = lower > 0.0
        equivalent = lower > -margins[endpoint] and upper < margins[endpoint]
        endpoint_rows[endpoint] = {
            "estimate": estimate,
            "lower": lower,
            "upper": upper,
            "margin": margins[endpoint],
            "superior": superior,
            "equivalent": equivalent,
            "n_blocks": len(values),
        }
        superiority.append(superior)
        equivalence.append(equivalent)

    tail_seen: dict[str, tuple[bool, bool]] = {}
    for row in tail_rows:
        if set(row) != {"block_id", "treatment_catastrophic", "control_catastrophic"}:
            raise ValueError("raw tail row field set mismatch")
        block = str(row["block_id"])
        if block in tail_seen:
            raise ValueError("duplicate tail block")
        tail_seen[block] = (bool(row["treatment_catastrophic"]), bool(row["control_catastrophic"]))
    if set(tail_seen) != set(blocks):
        raise ValueError("raw tail universe mismatch")
    n = len(blocks)
    t_events = sum(tail_seen[b][0] for b in blocks)
    c_events = sum(tail_seen[b][1] for b in blocks)
    tail_alpha = alpha / 2.0
    upper_difference = _cp_upper(t_events, n, tail_alpha) - _cp_lower(c_events, n, tail_alpha)
    tail_pass = upper_difference < float(plan["catastrophic_margin"])
    endpoint_rows["TAIL"] = {
        "method": TAIL_METHOD,
        "n": n,
        "treatment_events": t_events,
        "control_events": c_events,
        "risk_t": t_events / n,
        "risk_c": c_events / n,
        "upper_difference": upper_difference,
        "margin": float(plan["catastrophic_margin"]),
        "pass": tail_pass,
    }
    sup = all(superiority) and tail_pass
    eq = all(equivalence) and tail_pass
    verdict = "JOINT_SUPERIORITY" if sup else "JOINT_EQUIVALENCE_ON_NAMED_ESTIMANDS" if eq else "INCONCLUSIVE_OR_NON_EQUIVALENT"
    return {
        "plan_id": plan["plan_id"],
        "plan_digest": expected_plan_digest,
        "endpoint_rows": endpoint_rows,
        "superiority": sup,
        "equivalence": eq,
        "tail_gate_pass": tail_pass,
        "verdict": verdict,
    }
