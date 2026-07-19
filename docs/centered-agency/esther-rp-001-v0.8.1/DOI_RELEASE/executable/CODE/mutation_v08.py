from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from common_v08 import sha256_digest


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
        "CODE/formal_v08.py",
        "if cut != self._next_cut:",
        "if False and cut != self._next_cut:",
        "M01_PREFIX_GUARD",
        "MUTANT_M01_PREFIX_GUARD",
    ),
    MutantSpec(
        "M02_REQUEST_PREVALIDATION",
        "CODE/formal_v08.py",
        "if len(request_ids) != len(set(request_ids)):",
        "if False and len(request_ids) != len(set(request_ids)):",
        "M02_REQUEST_PREVALIDATION",
        "MUTANT_M02_ATOMIC_CUT",
    ),
    MutantSpec(
        "M03_CANONICAL_CREATION",
        "CODE/formal_v08.py",
        "if token.status is not ObligationStatus.CREATED:\n            raise ValueError(\"public creation requires CREATED status\")",
        "if False and token.status is not ObligationStatus.CREATED:\n            raise ValueError(\"public creation requires CREATED status\")",
        "M03_CANONICAL_CREATION",
        "MUTANT_M03_CREATION_GUARD",
    ),
    MutantSpec(
        "M04_ESCALATION_CHANGES_DEBTOR",
        "CODE/formal_v08.py",
        "operational_handler=token.escalation_to,",
        "normative_debtor=token.escalation_to,",
        "M04_ESCALATION_CHANGES_DEBTOR",
        "MUTANT_M04_ESCALATION_TRANSFER",
    ),
    MutantSpec(
        "M05_EVIDENCE_REBIND",
        "CODE/epistemic_v08.py",
        "if prior.content_digest != evidence.content_digest:",
        "if False and prior.content_digest != evidence.content_digest:",
        "M05_EVIDENCE_REBIND",
        "MUTANT_M05_EVIDENCE_BINDING",
    ),
    MutantSpec(
        "M06_UNMODELED_SOC_ACTION",
        "CODE/epistemic_v08.py",
        'return SOCDecision(None, None, "NO_SAFE_ACTION", (), relevant_models, evi, universe_digest)',
        'return SOCDecision("UNMODELED", DecisionKind.ACQUIRE_INFORMATION, "NO_SAFE_ACTION", (), relevant_models, evi, universe_digest)',
        "M06_UNMODELED_SOC_ACTION",
        "MUTANT_M06_SOC_UNIVERSE",
    ),
    MutantSpec(
        "M07_REQUEST_REBIND",
        "CODE/sioc_v08.py",
        "return self._mismatch_receipt(request)",
        "return prior_receipt",
        "M07_REQUEST_REBIND",
        "MUTANT_M07_REQUEST_BINDING",
    ),
    MutantSpec(
        "M08_ASSIGNMENT_DIGEST_BYPASS",
        "CODE/endpoint_v08.py",
        "if expected != manifest.digest:",
        "if False and expected != manifest.digest:",
        "M08_ASSIGNMENT_DIGEST_BYPASS",
        "MUTANT_M08_ASSIGNMENT_BINDING",
    ),
    MutantSpec(
        "M09_PLAN_DIGEST_BYPASS",
        "CODE/analysis_v08.py",
        "if expected != plan.digest:",
        "if False and expected != plan.digest:",
        "M09_PLAN_DIGEST_BYPASS",
        "MUTANT_M09_PLAN_BINDING",
    ),
    MutantSpec(
        "M10_AUTHORITY_OPTIONAL",
        "CODE/sioc_v08.py",
        'if decision is None:\n        raise RequestRejected("AUTHORITY_DECISION_MISSING")',
        'if decision is None:\n        return None',
        "M10_AUTHORITY_OPTIONAL",
        "MUTANT_M10_AUTHORITY_EFFECT",
    ),
    MutantSpec(
        "M11_SECONDARY_RANGE_BYPASS",
        "CODE/analysis_independent_v08.py",
        "if not 0 <= value <= 1:",
        "if False and not 0 <= value <= 1:",
        "M11_SECONDARY_RANGE_BYPASS",
        "MUTANT_M11_SECONDARY_VALIDATION",
    ),
    MutantSpec(
        "M12_GENERIC_FAILURE_AS_KILL",
        "CODE/mutation_v08.py",
        '    if expected_marker in output:\n        return "KILLED"',
        '    if exit_code != 0:\n        return "KILLED"',
        "M12_GENERIC_FAILURE_AS_KILL",
        "MUTANT_M12_ATTRIBUTION",
    ),
    MutantSpec(
        "M13_RECONCILIATION_CLAIM_UPGRADE",
        "CODE/formal_v08.py",
        "semantic_validity_claim=False,",
        "semantic_validity_claim=True,",
        "M13_RECONCILIATION_CLAIM_UPGRADE",
        "MUTANT_M13_RECONCILIATION_CEILING",
        replace_all=True,
    ),
    MutantSpec(
        "M14_EMPTY_CUT_REJECT",
        "CODE/formal_v08.py",
        "        for event in events:\n            event.validate()",
        "        if not events:\n            raise ValueError(\"mutant rejects empty cut\")\n        for event in events:\n            event.validate()",
        "M14_EMPTY_CUT_REJECT",
        "MUTANT_M14_EMPTY_CUT",
    ),
    MutantSpec(
        "M15_PREFIX_BINDING_BYPASS",
        "CODE/sioc_v08.py",
        '        "closed_prefix_digest": trusted_prefix.closed_prefix_digest,\n        "authority_source_id": trusted_prefix.authority_source_id,',
        '        "closed_prefix_digest": decision.closed_prefix_digest,\n        "authority_source_id": decision.authority_source_id,',
        "M15_PREFIX_BINDING_BYPASS",
        "MUTANT_M15_PREFIX_BINDING",
    ),
    MutantSpec(
        "M16_UNIT_RECEIPT_BYPASS",
        "CODE/finalize_reports_v08.py",
        '    result["verified_pass"] = digest_valid and fields_valid and execution_valid and artifact_evidence_valid',
        '    result["verified_pass"] = digest_valid and fields_valid and artifact_evidence_valid',
        "M16_UNIT_RECEIPT_BYPASS",
        "MUTANT_M16_FULL_TEST_EVIDENCE",
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
    command = [sys.executable, "TESTS/mutation_runner_v08.py", target_id]
    proc = subprocess.run(command, cwd=root, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    return {"command": command, "exit_code": proc.returncode, "output": proc.stdout}


def run_mutation_specs(package_root: Path, specs: tuple[MutantSpec, ...]) -> list[dict]:
    results: list[dict] = []
    for index, spec in enumerate(specs, 1):
        print(f"mutation {index}/{len(specs)} {spec.mutant_id}", file=sys.stderr, flush=True)
        with tempfile.TemporaryDirectory(prefix=f"esther-v08-{spec.mutant_id.lower()}-") as td:
            mutant_root = Path(td) / "candidate"
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
    return results


def build_report(results: list[dict]) -> dict:
    expected_ids = [spec.mutant_id for spec in MUTANTS]
    observed_ids = [item.get("mutant_id") for item in results]
    identity_valid = sorted(observed_ids) == sorted(expected_ids) and len(set(observed_ids)) == len(expected_ids)
    unrelated = classify_mutant_process(
        exit_code=1,
        output="ValueError: unrelated setup failure",
        expected_marker="MUTANT_EXPECTED",
        target_node="test_target",
    )
    counts = {status: sum(1 for item in results if item.get("status") == status) for status in ("KILLED", "SURVIVED", "ERROR")}
    return {
        "schema": "esther.rp001.v0.8.mutation_report.v1",
        "execution_mode": "four_isolated_shards",
        "declared_mutants": len(MUTANTS),
        "executed_mutants": len(results),
        "mutant_identity_valid": identity_valid,
        "results": sorted(results, key=lambda x: expected_ids.index(x.get("mutant_id")) if x.get("mutant_id") in expected_ids else 999),
        "counts": counts,
        "unrelated_failure_control": unrelated,
        "pass": identity_valid and counts["KILLED"] == len(MUTANTS) and counts["SURVIVED"] == 0 and counts["ERROR"] == 0 and unrelated == "ERROR",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--single", choices=[spec.mutant_id for spec in MUTANTS])
    parser.add_argument("--shard", type=int, choices=range(4))
    parser.add_argument("--merge", nargs="*")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.single is not None:
        specs = tuple(spec for spec in MUTANTS if spec.mutant_id == args.single)
        payload = {
            "schema": "esther.rp001.v0.8.mutation_single.v1",
            "mutant_id": args.single,
            "results": run_mutation_specs(root, specs),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["results"] and payload["results"][0].get("status") == "KILLED" else 1
    if args.shard is not None:
        specs = tuple(MUTANTS[args.shard * 4:(args.shard + 1) * 4])
        payload = {
            "schema": "esther.rp001.v0.8.mutation_shard.v1",
            "shard": args.shard,
            "results": run_mutation_specs(root, specs),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if all(item.get("status") == "KILLED" for item in payload["results"]) else 1
    if args.merge:
        results: list[dict] = []
        for filename in args.merge:
            payload = json.loads(Path(filename).read_text(encoding="utf-8"))
            results.extend(payload.get("results", []))
        report = build_report(results)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["pass"] else 1
    parser.error("use --single <mutant>, --shard 0..3, or --merge <files>")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
