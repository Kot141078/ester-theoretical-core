from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from decimal import Decimal
from enum import Enum
from typing import Any


class ObligationStatus(str, Enum):
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    TRANSFER_PENDING = "TRANSFER_PENDING"
    SATISFIED = "SATISFIED"
    VIOLATED = "VIOLATED"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"
    IMPOSSIBLE = "IMPOSSIBLE"
    TRANSFERRED = "TRANSFERRED"


TERMINAL_OBLIGATION_STATUSES = frozenset(
    {
        ObligationStatus.SATISFIED,
        ObligationStatus.VIOLATED,
        ObligationStatus.RELEASED,
        ObligationStatus.CANCELLED,
        ObligationStatus.IMPOSSIBLE,
        ObligationStatus.TRANSFERRED,
    }
)


class EvidenceStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    PROVISIONAL = "PROVISIONAL"
    CONTESTED = "CONTESTED"
    QUARANTINED = "QUARANTINED"
    REJECTED = "REJECTED"


class ResponseStatus(str, Enum):
    ANSWERED = "ANSWERED"
    UNRESOLVED = "UNRESOLVED"
    REFUSED = "REFUSED"
    TIMEOUT = "TIMEOUT"
    OMITTED = "OMITTED"
    INVALID = "INVALID"


class DecisionKind(str, Enum):
    DOMAIN = "DOMAIN"
    ACQUIRE_INFORMATION = "ACQUIRE_INFORMATION"
    ESCALATE = "ESCALATE"


def require_nonempty_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty text")
    return value


def require_nonnegative_int(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def require_finite_number(value: float | int | Decimal, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def canonicalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return canonicalize(dataclasses.asdict(value))
    if isinstance(value, Enum):
        return canonicalize(value.value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {str(k): canonicalize(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [canonicalize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        normalized = [canonicalize(v) for v in value]
        return sorted(normalized, key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True))
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value cannot be canonicalized")
        return value
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
