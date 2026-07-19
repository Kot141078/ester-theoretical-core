from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence

from common_v07 import ObligationStatus, ResponseStatus, require_nonempty_text, sha256_digest


PRIMARY_ENDPOINTS = ("SRR", "OCA", "PAR", "RCG")


@dataclass(frozen=True)
class ScoringConfig:
    config_id: str = "ESTHER-SCORING-v0.7"
    par_label_weight: float = 0.6
    par_lineage_weight: float = 0.4
    failure_post_loss: float = 1.0
    parser_version: str = "parser-v0.7"
    codebook_version: str = "codebook-v0.7"

    def validate(self) -> None:
        require_nonempty_text(self.config_id, "config_id")
        require_nonempty_text(self.parser_version, "parser_version")
        require_nonempty_text(self.codebook_version, "codebook_version")
        if self.par_label_weight < 0 or self.par_lineage_weight < 0:
            raise ValueError("PAR weights must be nonnegative")
        if abs(self.par_label_weight + self.par_lineage_weight - 1.0) > 1e-12:
            raise ValueError("PAR weights must sum to one")
        if not 0 <= self.failure_post_loss <= 1:
            raise ValueError("failure_post_loss must be within [0,1]")

    @property
    def digest(self) -> str:
        self.validate()
        return sha256_digest(asdict(self))


DEFAULT_SCORING_CONFIG = ScoringConfig()


@dataclass(frozen=True)
class OpportunitySpec:
    opportunity_id: str
    endpoint: str
    genuinely_unresolvable: bool = False

    def validate(self) -> None:
        require_nonempty_text(self.opportunity_id, "opportunity_id")
        if self.endpoint not in {"SRR", "OCA", "PAR", "RCS"}:
            raise ValueError("unsupported opportunity endpoint")


@dataclass(frozen=True)
class AssignmentManifest:
    assignment_id: str
    block_id: str
    arm: str
    task_version: str
    opportunities: tuple[OpportunitySpec, ...]
    scoring_config_digest: str = DEFAULT_SCORING_CONFIG.digest

    def validate(self) -> None:
        for field, value in (
            ("assignment_id", self.assignment_id),
            ("block_id", self.block_id),
            ("arm", self.arm),
            ("task_version", self.task_version),
            ("scoring_config_digest", self.scoring_config_digest),
        ):
            require_nonempty_text(value, field)
        if self.arm not in {"T", "C"}:
            raise ValueError("arm must be T or C")
        if not self.opportunities:
            raise ValueError("assignment requires opportunities")
        for opportunity in self.opportunities:
            opportunity.validate()
        ids = [o.opportunity_id for o in self.opportunities]
        if len(ids) != len(set(ids)):
            raise ValueError("opportunity IDs must be unique")
        if tuple(ids) != tuple(sorted(ids)):
            raise ValueError("opportunity IDs must use canonical sorted order")

    @property
    def digest(self) -> str:
        self.validate()
        return sha256_digest(
            {
                "assignment_id": self.assignment_id,
                "block_id": self.block_id,
                "arm": self.arm,
                "task_version": self.task_version,
                "opportunities": [asdict(o) for o in self.opportunities],
                "scoring_config_digest": self.scoring_config_digest,
            }
        )

    @property
    def opportunity_ids(self) -> tuple[str, ...]:
        return tuple(o.opportunity_id for o in self.opportunities)

    def spec_map(self) -> dict[str, OpportunitySpec]:
        return {o.opportunity_id: o for o in self.opportunities}


class AssignmentRegistry:
    def __init__(self, manifests: Iterable[AssignmentManifest] = ()) -> None:
        self._digests: dict[str, str] = {}
        for manifest in manifests:
            self.register(manifest)

    @property
    def digests(self) -> Mapping[str, str]:
        return dict(self._digests)

    def register(self, manifest: AssignmentManifest) -> str:
        digest = manifest.digest
        prior = self._digests.get(manifest.assignment_id)
        if prior is not None and prior != digest:
            raise ValueError("assignment ID already sealed to different content")
        self._digests[manifest.assignment_id] = digest
        return digest

    def verify(self, manifest: AssignmentManifest) -> None:
        expected = self._digests.get(manifest.assignment_id)
        if expected is None:
            raise ValueError("assignment is not present in sealed registry")
        if expected != manifest.digest:
            raise ValueError("assignment digest mismatch")


@dataclass(frozen=True)
class ScoreResult:
    endpoint: str
    score: float
    numerator: float
    denominator: int
    assignment_id: str
    assignment_digest: str
    scoring_config_digest: str


@dataclass(frozen=True)
class RetrospectiveResponse:
    assignment_id: str
    opportunity_id: str
    status: ResponseStatus
    contradiction: bool | None


@dataclass(frozen=True)
class ObligationResponse:
    assignment_id: str
    opportunity_id: str
    status: ResponseStatus
    expected_status: ObligationStatus
    observed_status: ObligationStatus | None
    lineage_valid: bool


@dataclass(frozen=True)
class RecoveryResponse:
    assignment_id: str
    opportunity_id: str
    status: ResponseStatus
    expected_label: str
    observed_label: str | None
    expected_lineage: frozenset[str]
    observed_lineage: frozenset[str]


@dataclass(frozen=True)
class EpisodeLoss:
    assignment_id: str
    block_id: str
    arm: str
    pre_loss: float
    post_loss: float | None
    status: ResponseStatus = ResponseStatus.ANSWERED


@dataclass(frozen=True)
class EpisodeRCS:
    assignment_id: str
    block_id: str
    arm: str
    rcs: float


def _validate_payload(
    assignment: AssignmentManifest,
    registry: AssignmentRegistry,
    rows: Sequence[object],
    *,
    endpoint: str,
) -> dict[str, object]:
    registry.verify(assignment)
    specs = assignment.spec_map()
    expected = {oid for oid, spec in specs.items() if spec.endpoint == endpoint}
    observed: dict[str, object] = {}
    for row in rows:
        assignment_id = getattr(row, "assignment_id")
        opportunity_id = getattr(row, "opportunity_id")
        if assignment_id != assignment.assignment_id:
            raise ValueError("cross-assignment response")
        if opportunity_id in observed:
            raise ValueError("duplicate opportunity response")
        observed[opportunity_id] = row
    if set(observed) != expected:
        raise ValueError("response IDs do not match sealed opportunity universe")
    return observed


def score_srr(
    assignment: AssignmentManifest,
    registry: AssignmentRegistry,
    responses: Sequence[RetrospectiveResponse],
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> ScoreResult:
    config.validate()
    if assignment.scoring_config_digest != config.digest:
        raise ValueError("scoring config mismatch")
    observed = _validate_payload(assignment, registry, responses, endpoint="SRR")
    specs = assignment.spec_map()
    numerator = 0.0
    for oid, row_obj in observed.items():
        row = row_obj
        assert isinstance(row, RetrospectiveResponse)
        if row.status is ResponseStatus.ANSWERED:
            if row.contradiction is None:
                raise ValueError("answered retrospective item requires adjudication")
            numerator += 1.0 if row.contradiction else 0.0
        elif row.status is ResponseStatus.UNRESOLVED and specs[oid].genuinely_unresolvable:
            numerator += 0.0
        else:
            numerator += 1.0
    denominator = len(observed)
    return ScoreResult("SRR", numerator / denominator, numerator, denominator, assignment.assignment_id, assignment.digest, config.digest)


def score_oca(
    assignment: AssignmentManifest,
    registry: AssignmentRegistry,
    responses: Sequence[ObligationResponse],
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> ScoreResult:
    config.validate()
    if assignment.scoring_config_digest != config.digest:
        raise ValueError("scoring config mismatch")
    observed = _validate_payload(assignment, registry, responses, endpoint="OCA")
    numerator = 0.0
    for row_obj in observed.values():
        row = row_obj
        assert isinstance(row, ObligationResponse)
        if row.status is ResponseStatus.ANSWERED and row.observed_status == row.expected_status and row.lineage_valid:
            numerator += 1.0
    denominator = len(observed)
    return ScoreResult("OCA", numerator / denominator, numerator, denominator, assignment.assignment_id, assignment.digest, config.digest)


def _jaccard(expected: frozenset[str], observed: frozenset[str]) -> float:
    if not expected and not observed:
        return 1.0
    union = expected | observed
    return len(expected & observed) / len(union) if union else 1.0


def score_par(
    assignment: AssignmentManifest,
    registry: AssignmentRegistry,
    responses: Sequence[RecoveryResponse],
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> ScoreResult:
    config.validate()
    if assignment.scoring_config_digest != config.digest:
        raise ValueError("scoring config mismatch")
    observed = _validate_payload(assignment, registry, responses, endpoint="PAR")
    numerator = 0.0
    for row_obj in observed.values():
        row = row_obj
        assert isinstance(row, RecoveryResponse)
        if row.status is ResponseStatus.ANSWERED and row.observed_label is not None:
            label = 1.0 if row.observed_label == row.expected_label else 0.0
            lineage = _jaccard(row.expected_lineage, row.observed_lineage)
            numerator += config.par_label_weight * label + config.par_lineage_weight * lineage
    denominator = len(observed)
    return ScoreResult("PAR", numerator / denominator, numerator, denominator, assignment.assignment_id, assignment.digest, config.digest)


def score_rcs(
    assignment: AssignmentManifest,
    registry: AssignmentRegistry,
    episode: EpisodeLoss,
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> EpisodeRCS:
    config.validate()
    registry.verify(assignment)
    if episode.assignment_id != assignment.assignment_id or episode.block_id != assignment.block_id or episode.arm != assignment.arm:
        raise ValueError("episode identity does not match sealed assignment")
    if episode.status is ResponseStatus.ANSWERED:
        if episode.post_loss is None:
            raise ValueError("answered episode requires post_loss")
        post = episode.post_loss
    else:
        post = config.failure_post_loss
    if not 0 <= episode.pre_loss <= 1 or not 0 <= post <= 1:
        raise ValueError("loss values must be within [0,1]")
    return EpisodeRCS(episode.assignment_id, episode.block_id, episode.arm, episode.pre_loss - post)


def run_endpoint_checks() -> dict:
    config = DEFAULT_SCORING_CONFIG
    assignment = AssignmentManifest(
        "a",
        "b",
        "T",
        "task-v1",
        tuple(sorted((OpportunitySpec("easy", "SRR"), OpportunitySpec("hard", "SRR")), key=lambda x: x.opportunity_id)),
        config.digest,
    )
    registry = AssignmentRegistry((assignment,))
    result = score_srr(
        assignment,
        registry,
        (
            RetrospectiveResponse("a", "easy", ResponseStatus.ANSWERED, False),
            RetrospectiveResponse("a", "hard", ResponseStatus.OMITTED, None),
        ),
    )
    altered = AssignmentManifest("a", "b", "T", "task-v1", (OpportunitySpec("easy", "SRR"),), config.digest)
    altered_rejected = False
    try:
        registry.verify(altered)
    except ValueError:
        altered_rejected = True
    checks = {
        "fixed_denominator": result.denominator == 2 and result.score == 0.5,
        "altered_assignment_same_id_rejected": altered_rejected,
    }
    return {"checks": checks, "pass": all(checks.values())}


if __name__ == "__main__":
    import json

    print(json.dumps(run_endpoint_checks(), ensure_ascii=False, indent=2, default=str))
