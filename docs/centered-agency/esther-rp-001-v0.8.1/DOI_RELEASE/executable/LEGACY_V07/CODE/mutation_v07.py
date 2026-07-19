from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from common_v07 import sha256_digest


@dataclass(frozen=True)
class MutantSpec:
    mutant_id: str
    source_path: str
    old: str
    new: str
    target_node: str
    expected_marker: str
    replace_all: bool = False


def classify_mutant_process(*, exit_code: int, output: str, expected_marker: str, target_node: str) -> str:
    if exit_code == 0:
        return "SURVIVED"
    if expected_marker in output:
        return "KILLED"
    return "ERROR"


MUTANTS = (
    MutantSpec(
        "M01_PREFIX_GUARD",
        "CODE/formal_v07.py",
        "if cut != self._next_cut:",
        "if False and cut != self._next_cut:",
        "M01_PREFIX_GUARD",
        "MUTANT_M01_PREFIX_GUARD",
    ),
    MutantSpec(
        "M02_REQUEST_PREVALIDATION",
        "CODE/formal_v07.py",
        "if len(request_ids) != len(set(request_ids)):",
        "if False and len(request_ids) != len(set(request_ids)):",
        "M02_REQUEST_PREVALIDATION",
        "MUTANT_M02_ATOMIC_CUT",
    ),
    MutantSpec(
        "M03_CANONICAL_CREATION",
        "CODE/formal_v07.py",
        "if token.status is not ObligationStatus.CREATED:\n            raise ValueError(\"public creation requires CREATED status\")",
        "if False and token.status is not ObligationStatus.CREATED:\n            raise ValueError(\"public creation requires CREATED status\")",
        "M03_CANONICAL_CREATION",
        "MUTANT_M03_CREATION_GUARD",
    ),
    MutantSpec(
        "M04_ESCALATION_CHANGES_DEBTOR",
        "CODE/formal_v07.py",
        "operational_handler=token.escalation_to,",
        "normative_debtor=token.escalation_to,",
        "M04_ESCALATION_CHANGES_DEBTOR",
        "MUTANT_M04_ESCALATION_TRANSFER",
    ),
    MutantSpec(
        "M05_EVIDENCE_REBIND",
        "CODE/epistemic_v07.py",
        "if prior.content_digest != evidence.content_digest:",
        "if False and prior.content_digest != evidence.content_digest:",
        "M05_EVIDENCE_REBIND",
        "MUTANT_M05_EVIDENCE_BINDING",
    ),
    MutantSpec(
        "M06_UNMODELED_SOC_ACTION",
        "CODE/epistemic_v07.py",
        'return SOCDecision(None, None, "NO_SAFE_ACTION", (), relevant_models, evi, universe_digest)',
        'return SOCDecision("UNMODELED", DecisionKind.ACQUIRE_INFORMATION, "NO_SAFE_ACTION", (), relevant_models, evi, universe_digest)',
        "M06_UNMODELED_SOC_ACTION",
        "MUTANT_M06_SOC_UNIVERSE",
    ),
    MutantSpec(
        "M07_REQUEST_REBIND",
        "CODE/sioc_v07.py",
        "return self._mismatch_receipt(request)",
        "return prior_receipt",
        "M07_REQUEST_REBIND",
        "MUTANT_M07_REQUEST_BINDING",
    ),
    MutantSpec(
        "M08_ASSIGNMENT_DIGEST_BYPASS",
        "CODE/endpoint_v07.py",
        "if expected != manifest.digest:",
        "if False and expected != manifest.digest:",
        "M08_ASSIGNMENT_DIGEST_BYPASS",
        "MUTANT_M08_ASSIGNMENT_BINDING",
    ),
    MutantSpec(
        "M09_PLAN_DIGEST_BYPASS",
        "CODE/analysis_v07.py",
        "if expected != plan.digest:",
        "if False and expected != plan.digest:",
        "M09_PLAN_DIGEST_BYPASS",
        "MUTANT_M09_PLAN_BINDING",
    ),
    MutantSpec(
        "M10_AUTHORITY_OPTIONAL",
        "CODE/sioc_v07.py",
        'if decision is None:\n        raise RequestRejected("AUTHORITY_DECISION_MISSING")',
        'if decision is None:\n        return None',
        "M10_AUTHORITY_OPTIONAL",
        "MUTANT_M10_AUTHORITY_EFFECT",
    ),
    MutantSpec(
        "M11_SECONDARY_RANGE_BYPASS",
        "CODE/analysis_independent_v07.py",
        "if not 0 <= value <= 1:",
        "if False and not 0 <= value <= 1:",
        "M11_SECONDARY_RANGE_BYPASS",
        "MUTANT_M11_SECONDARY_VALIDATION",
    ),
    MutantSpec(
        "M12_GENERIC_FAILURE_AS_KILL",
        "CODE/mutation_v07.py",
        '    if expected_marker in output:\n        return "KILLED"',
        '    if exit_code != 0:\n        return "KILLED"',
        "M12_GENERIC_FAILURE_AS_KILL",
        "MUTANT_M12_ATTRIBUTION",
    ),
    MutantSpec(
        "M13_RECONCILIATION_CLAIM_UPGRADE",
        "CODE/formal_v07.py",
        "semantic_validity_claim=False,",
        "semantic_validity_claim=True,",
        "M13_RECONCILIATION_CLAIM_UPGRADE",
        "MUTANT_M13_RECONCILIATION_CEILING",
        replace_all=True,
    ),
)


def _run_target(root: Path, target_id: str) -> dict:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "CODE")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["OPENBLAS_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    env["MKL_NUM_THREADS"] = "1"
    command = [sys.executable, "TESTS/mutation_runner_v07.py", target_id]
    proc = subprocess.run(command, cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    return {"command": command, "exit_code": proc.returncode, "output": proc.stdout}


def run_mutation_harness(package_root: str | Path | None = None) -> dict:
    package_root = Path(package_root) if package_root is not None else Path(__file__).resolve().parents[1]
    results = []
    with tempfile.TemporaryDirectory(prefix="esther-v07-mutants-") as td:
        temp_root = Path(td)
        for spec in MUTANTS:
            mutant_root = temp_root / spec.mutant_id
            ignore = shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache")
            shutil.copytree(package_root / "CODE", mutant_root / "CODE", ignore=ignore)
            shutil.copytree(package_root / "TESTS", mutant_root / "TESTS", ignore=ignore)
            baseline = _run_target(mutant_root, spec.target_node)
            if baseline["exit_code"] != 0:
                results.append({
                    "mutant_id": spec.mutant_id,
                    "status": "ERROR",
                    "reason": "baseline target did not pass",
                    "baseline": baseline,
                })
                continue

            source = mutant_root / spec.source_path
            text = source.read_text(encoding="utf-8")
            count = text.count(spec.old)
            if count == 0 or (count != 1 and not spec.replace_all):
                results.append({
                    "mutant_id": spec.mutant_id,
                    "status": "ERROR",
                    "reason": f"mutation site count {count}",
                    "baseline": baseline,
                })
                continue
            mutated = text.replace(spec.old, spec.new) if spec.replace_all else text.replace(spec.old, spec.new, 1)
            source.write_text(mutated, encoding="utf-8")
            diff_digest = sha256_digest({"source": spec.source_path, "old": spec.old, "new": spec.new, "count": count})
            run = _run_target(mutant_root, spec.target_node)
            status = classify_mutant_process(
                exit_code=run["exit_code"],
                output=run["output"],
                expected_marker=spec.expected_marker,
                target_node=spec.target_node,
            )
            results.append({
                "mutant_id": spec.mutant_id,
                "source_path": spec.source_path,
                "site_count": count,
                "diff_digest": diff_digest,
                "target_node": spec.target_node,
                "expected_marker": spec.expected_marker,
                "baseline_exit": baseline["exit_code"],
                "mutated_exit": run["exit_code"],
                "status": status,
                "output_tail": run["output"][-2000:],
            })

    # Controlled unrelated failure must be ERROR, not KILLED.
    unrelated = classify_mutant_process(
        exit_code=1,
        output="ValueError: unrelated setup failure",
        expected_marker="MUTANT_EXPECTED",
        target_node="test_target",
    )
    counts = {status: sum(1 for item in results if item["status"] == status) for status in ("KILLED", "SURVIVED", "ERROR")}
    return {
        "declared_mutants": len(MUTANTS),
        "executed_mutants": len(results),
        "results": results,
        "counts": counts,
        "unrelated_failure_control": unrelated,
        "pass": counts["KILLED"] == len(MUTANTS) and counts["SURVIVED"] == 0 and counts["ERROR"] == 0 and unrelated == "ERROR",
    }


if __name__ == "__main__":
    report = run_mutation_harness()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["pass"] else 1)
