from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite, sqrt
from statistics import mean, stdev
from typing import Iterable, Mapping, Sequence

from scipy.stats import beta, t

from common_v07 import require_nonempty_text, sha256_digest
from endpoint_v07 import EpisodeRCS, PRIMARY_ENDPOINTS


TAIL_METHOD = "BONFERRONI_CP_RISK_DIFFERENCE_V1"
SOFTWARE_PROFILE = ("analysis-v0.7", "scipy-t-beta")


@dataclass(frozen=True)
class AnalysisPlan:
    plan_id: str
    endpoint_names: tuple[str, ...]
    expected_block_ids: tuple[str, ...]
    margins: tuple[tuple[str, float], ...]
    family_alpha: float
    catastrophic_margin: float
    scoring_config_digest: str
    tail_method: str = TAIL_METHOD
    software_profile: tuple[str, ...] = SOFTWARE_PROFILE

    def validate(self) -> None:
        require_nonempty_text(self.plan_id, "plan_id")
        require_nonempty_text(self.scoring_config_digest, "scoring_config_digest")
        if self.endpoint_names != PRIMARY_ENDPOINTS:
            raise ValueError("analysis plan requires exact primary endpoint order")
        if not self.expected_block_ids or len(self.expected_block_ids) != len(set(self.expected_block_ids)):
            raise ValueError("expected block IDs must be nonempty and unique")
        if tuple(self.expected_block_ids) != tuple(sorted(self.expected_block_ids)):
            raise ValueError("block IDs must use canonical sorted order")
        margin_map = dict(self.margins)
        if len(margin_map) != len(self.margins) or set(margin_map) != set(PRIMARY_ENDPOINTS):
            raise ValueError("margins must name exactly four primary endpoints")
        if any((not isfinite(v)) or v <= 0 for v in margin_map.values()):
            raise ValueError("equivalence margins must be finite and positive")
        if not isfinite(self.family_alpha) or not 0 < self.family_alpha < 1:
            raise ValueError("family_alpha must be within (0,1)")
        if not isfinite(self.catastrophic_margin) or not 0 < self.catastrophic_margin < 1:
            raise ValueError("catastrophic margin must be within (0,1)")
        if self.tail_method != TAIL_METHOD:
            raise ValueError("tail method is not the frozen method")
        if self.software_profile != SOFTWARE_PROFILE:
            raise ValueError("software profile mismatch")

    @property
    def margin_map(self) -> dict[str, float]:
        return dict(self.margins)

    @property
    def digest(self) -> str:
        self.validate()
        return sha256_digest(asdict(self))


class AnalysisPlanRegistry:
    def __init__(self, plans: Iterable[AnalysisPlan] = ()) -> None:
        self._digests: dict[str, str] = {}
        for plan in plans:
            self.register(plan)

    @property
    def digests(self) -> Mapping[str, str]:
        return dict(self._digests)

    def register(self, plan: AnalysisPlan) -> str:
        digest = plan.digest
        prior = self._digests.get(plan.plan_id)
        if prior is not None and prior != digest:
            raise ValueError("plan ID already sealed to different content")
        self._digests[plan.plan_id] = digest
        return digest

    def verify(self, plan: AnalysisPlan) -> None:
        expected = self._digests.get(plan.plan_id)
        if expected is None:
            raise ValueError("analysis plan is not sealed in registry")
        if expected != plan.digest:
            raise ValueError("analysis plan digest mismatch")


@dataclass(frozen=True)
class BlockEndpoint:
    block_id: str
    endpoint: str
    treatment_value: float
    control_value: float

    def validate(self) -> None:
        require_nonempty_text(self.block_id, "block_id")
        if self.endpoint not in PRIMARY_ENDPOINTS:
            raise ValueError("unknown endpoint")
        if not isfinite(self.treatment_value) or not isfinite(self.control_value):
            raise ValueError("endpoint values must be finite")
        if self.endpoint in {"SRR", "OCA", "PAR"}:
            if not 0 <= self.treatment_value <= 1 or not 0 <= self.control_value <= 1:
                raise ValueError("SRR/OCA/PAR values must be within [0,1]")
        else:
            if not -1 <= self.treatment_value <= 1 or not -1 <= self.control_value <= 1:
                raise ValueError("RCG/RCS values must be within [-1,1]")

    @property
    def contrast(self) -> float:
        self.validate()
        return (
            self.control_value - self.treatment_value
            if self.endpoint == "SRR"
            else self.treatment_value - self.control_value
        )


@dataclass(frozen=True)
class TailPair:
    block_id: str
    treatment_catastrophic: bool
    control_catastrophic: bool


@dataclass(frozen=True)
class AnalysisDecision:
    plan_id: str
    plan_digest: str
    endpoint_rows: dict[str, dict[str, float | bool | str]]
    superiority: bool
    equivalence: bool
    tail_gate_pass: bool
    verdict: str


def default_plan(blocks: Sequence[str], scoring_config_digest: str, *, plan_id: str = "ESTHER-PLAN-v0.7") -> AnalysisPlan:
    ordered = tuple(sorted(blocks))
    return AnalysisPlan(
        plan_id=plan_id,
        endpoint_names=PRIMARY_ENDPOINTS,
        expected_block_ids=ordered,
        margins=(("SRR", 0.05), ("OCA", 0.05), ("PAR", 0.05), ("RCG", 0.08)),
        family_alpha=0.05,
        catastrophic_margin=0.02,
        scoring_config_digest=scoring_config_digest,
    )


def _mean_ci(values: Sequence[float], alpha: float) -> tuple[float, float, float]:
    if len(values) < 2:
        raise ValueError("at least two blocks are required")
    estimate = mean(values)
    se = stdev(values) / sqrt(len(values))
    critical = float(t.ppf(1.0 - alpha / 2.0, len(values) - 1))
    return estimate, estimate - critical * se, estimate + critical * se


def _cp_upper(events: int, n: int, alpha: float) -> float:
    if n <= 0:
        raise ValueError("tail population cannot be empty")
    if events < 0 or events > n:
        raise ValueError("invalid event count")
    if events == n:
        return 1.0
    return float(beta.ppf(1.0 - alpha, events + 1, n - events))


def _cp_lower(events: int, n: int, alpha: float) -> float:
    if n <= 0:
        raise ValueError("tail population cannot be empty")
    if events < 0 or events > n:
        raise ValueError("invalid event count")
    if events == 0:
        return 0.0
    return float(beta.ppf(alpha, events, n - events + 1))


def catastrophic_tail_gate(
    pairs: Sequence[TailPair],
    *,
    expected_block_ids: Sequence[str],
    margin: float,
    family_alpha: float,
) -> dict[str, float | bool | str]:
    if not isfinite(margin) or margin <= 0:
        raise ValueError("tail margin must be positive")
    if not 0 < family_alpha < 1:
        raise ValueError("family alpha must be within (0,1)")
    ids = [p.block_id for p in pairs]
    if len(ids) != len(set(ids)) or set(ids) != set(expected_block_ids):
        raise ValueError("tail block universe mismatch")
    n = len(pairs)
    t_events = sum(bool(p.treatment_catastrophic) for p in pairs)
    c_events = sum(bool(p.control_catastrophic) for p in pairs)
    alpha_each = family_alpha / 2.0
    upper_difference = _cp_upper(t_events, n, alpha_each) - _cp_lower(c_events, n, alpha_each)
    return {
        "method": TAIL_METHOD,
        "n": n,
        "treatment_events": t_events,
        "control_events": c_events,
        "risk_t": t_events / n,
        "risk_c": c_events / n,
        "upper_difference": upper_difference,
        "margin": margin,
        "pass": upper_difference < margin,
    }


def analyze_named_estimands(
    rows: Sequence[BlockEndpoint],
    *,
    plan: AnalysisPlan,
    registry: AnalysisPlanRegistry,
    tail_pairs: Sequence[TailPair],
) -> AnalysisDecision:
    registry.verify(plan)
    expected_pairs = {(block, endpoint) for block in plan.expected_block_ids for endpoint in plan.endpoint_names}
    observed: dict[tuple[str, str], BlockEndpoint] = {}
    for row in rows:
        row.validate()
        key = (row.block_id, row.endpoint)
        if key in observed:
            raise ValueError("duplicate block/endpoint row")
        observed[key] = row
    if set(observed) != expected_pairs:
        raise ValueError("rows do not match sealed block/endpoint universe")

    alpha_each = plan.family_alpha / len(plan.endpoint_names)
    endpoint_rows: dict[str, dict[str, float | bool | str]] = {}
    superiority_flags: list[bool] = []
    equivalence_flags: list[bool] = []
    for endpoint in plan.endpoint_names:
        contrasts = [observed[(block, endpoint)].contrast for block in plan.expected_block_ids]
        estimate, lower, upper = _mean_ci(contrasts, alpha_each)
        margin = plan.margin_map[endpoint]
        superior = lower > 0.0
        equivalent = lower > -margin and upper < margin
        endpoint_rows[endpoint] = {
            "estimate": estimate,
            "lower": lower,
            "upper": upper,
            "margin": margin,
            "superior": superior,
            "equivalent": equivalent,
            "n_blocks": len(contrasts),
        }
        superiority_flags.append(superior)
        equivalence_flags.append(equivalent)

    tail = catastrophic_tail_gate(
        tail_pairs,
        expected_block_ids=plan.expected_block_ids,
        margin=plan.catastrophic_margin,
        family_alpha=plan.family_alpha,
    )
    endpoint_rows["TAIL"] = tail
    tail_pass = bool(tail["pass"])
    superiority = all(superiority_flags) and tail_pass
    equivalence = all(equivalence_flags) and tail_pass
    if superiority:
        verdict = "JOINT_SUPERIORITY"
    elif equivalence:
        verdict = "JOINT_EQUIVALENCE_ON_NAMED_ESTIMANDS"
    else:
        verdict = "INCONCLUSIVE_OR_NON_EQUIVALENT"
    return AnalysisDecision(plan.plan_id, plan.digest, endpoint_rows, superiority, equivalence, tail_pass, verdict)


def block_rcg(rows: Sequence[EpisodeRCS]) -> tuple[BlockEndpoint, ...]:
    by_block: dict[str, dict[str, EpisodeRCS]] = {}
    for row in rows:
        if row.arm not in {"T", "C"}:
            raise ValueError("arm must be T or C")
        arms = by_block.setdefault(row.block_id, {})
        if row.arm in arms:
            raise ValueError("duplicate arm in block")
        arms[row.arm] = row
    out: list[BlockEndpoint] = []
    for block, arms in sorted(by_block.items()):
        if set(arms) != {"T", "C"}:
            raise ValueError("RCG block requires one treatment and one control episode")
        out.append(BlockEndpoint(block, "RCG", arms["T"].rcs, arms["C"].rcs))
    return tuple(out)


def run_analysis_checks(scoring_config_digest: str) -> dict:
    blocks = tuple(f"b{i:03d}" for i in range(200))
    plan = default_plan(blocks, scoring_config_digest)
    registry = AnalysisPlanRegistry((plan,))
    rows = []
    for block in blocks:
        for endpoint in PRIMARY_ENDPOINTS:
            if endpoint == "SRR":
                rows.append(BlockEndpoint(block, endpoint, 0.2, 0.2))
            elif endpoint == "RCG":
                rows.append(BlockEndpoint(block, endpoint, 0.0, 0.0))
            else:
                rows.append(BlockEndpoint(block, endpoint, 0.5, 0.5))
    tail = [TailPair(block, False, False) for block in blocks]
    decision = analyze_named_estimands(rows, plan=plan, registry=registry, tail_pairs=tail)
    altered = AnalysisPlan(
        plan.plan_id,
        plan.endpoint_names,
        plan.expected_block_ids,
        tuple((e, 0.5) for e in plan.endpoint_names),
        plan.family_alpha,
        plan.catastrophic_margin,
        plan.scoring_config_digest,
    )
    altered_rejected = False
    try:
        registry.verify(altered)
    except ValueError:
        altered_rejected = True
    checks = {
        "sealed_plan_accepts_original": decision.plan_digest == plan.digest,
        "same_plan_id_changed_content_rejected": altered_rejected,
        "exact_endpoint_universe": set(decision.endpoint_rows) == set(PRIMARY_ENDPOINTS) | {"TAIL"},
    }
    return {"checks": checks, "verdict": decision.verdict, "pass": all(checks.values())}


if __name__ == "__main__":
    import json
    from endpoint_v07 import DEFAULT_SCORING_CONFIG

    print(json.dumps(run_analysis_checks(DEFAULT_SCORING_CONFIG.digest), ensure_ascii=False, indent=2, default=str))
