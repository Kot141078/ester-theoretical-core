from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import sys

import numpy
import pytest
import scipy

from analysis_independent_v08 import analyze_raw_fixture
from analysis_v08 import AnalysisPlanRegistry, BlockEndpoint, TailPair, analyze_named_estimands, default_plan
from common_v08 import file_sha256, sha256_digest
from endpoint_v08 import DEFAULT_SCORING_CONFIG, PRIMARY_ENDPOINTS

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "REPORTS"
REPORTS.mkdir(exist_ok=True)
CURRENT_EXPECTED_TESTS = 190
LEGACY_EXPECTED_TESTS = 177


def write_json(name: str, payload: object) -> None:
    (REPORTS / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(name: str) -> dict:
    return json.loads((REPORTS / name).read_text(encoding="utf-8"))


def _verify_artifact(path_text: object, expected_sha256: object, *, artifact_root: Path = ROOT) -> dict:
    result = {
        "declared_path": path_text,
        "declared_sha256": expected_sha256,
        "exists": False,
        "inside_package_root": False,
        "actual_sha256": None,
        "match": False,
    }
    if not isinstance(path_text, str) or not isinstance(expected_sha256, str):
        return result
    path = Path(path_text)
    if not path.is_absolute():
        path = artifact_root / path
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(artifact_root.resolve())
    except (FileNotFoundError, ValueError):
        return result
    result["exists"] = resolved.is_file()
    result["inside_package_root"] = True
    if result["exists"]:
        result["actual_sha256"] = file_sha256(str(resolved))
        result["match"] = result["actual_sha256"] == expected_sha256
    return result


def verify_test_receipt(receipt: dict, *, expected_suite: str, expected_tests: int, artifact_root: Path = ROOT) -> dict:
    payload = dict(receipt)
    observed_digest = payload.pop("receipt_digest", None)
    digest_valid = observed_digest == sha256_digest(payload)
    fields_valid = (
        receipt.get("schema") == "esther.rp001.v0.8.pytest_receipt.v1"
        and receipt.get("suite") == expected_suite
        and receipt.get("expected_tests") == expected_tests
        and receipt.get("execution_mode") == "full_pytest_junit"
    )
    execution_valid = (
        receipt.get("full_pytest_exit_code") == 0
        and receipt.get("collected_count") == expected_tests
        and receipt.get("executed_count") == expected_tests
        and receipt.get("passed_count") == expected_tests
        and receipt.get("failed_count") == 0
        and receipt.get("error_count") == 0
        and receipt.get("skipped_count") == 0
        and receipt.get("pass") is True
    )
    artifacts = {
        "junit": _verify_artifact(receipt.get("junit_path"), receipt.get("junit_sha256"), artifact_root=artifact_root),
        "stdout": _verify_artifact(receipt.get("stdout_path"), receipt.get("stdout_sha256"), artifact_root=artifact_root),
        "stderr": _verify_artifact(receipt.get("stderr_path"), receipt.get("stderr_sha256"), artifact_root=artifact_root),
    }
    artifact_evidence_valid = all(item["match"] for item in artifacts.values())
    result = dict(receipt)
    result["receipt_digest_valid"] = digest_valid
    result["contract_fields_valid"] = fields_valid
    result["execution_evidence_valid"] = execution_valid
    result["artifact_evidence"] = artifacts
    result["artifact_evidence_valid"] = artifact_evidence_valid
    result["verified_pass"] = digest_valid and fields_valid and execution_valid and artifact_evidence_valid
    return result


def build_unit_test_report(current_receipt: dict, legacy_receipt: dict, *, artifact_root: Path = ROOT) -> dict:
    current = verify_test_receipt(
        current_receipt, expected_suite="TESTS", expected_tests=CURRENT_EXPECTED_TESTS, artifact_root=artifact_root
    )
    legacy = verify_test_receipt(
        legacy_receipt,
        expected_suite="LEGACY_V07/TESTS",
        expected_tests=LEGACY_EXPECTED_TESTS,
        artifact_root=artifact_root,
    )
    return {
        "schema": "esther.rp001.v0.8.unit_test_report.v1",
        "execution_mode": "full_pytest_junit_receipts",
        "v0_8": current,
        "legacy_v0_7": legacy,
        "warnings_as_errors": True,
        "pass": current["verified_pass"] and legacy["verified_pass"],
    }


def fixture_rows(block_ids: tuple[str, ...], mode: str) -> list[BlockEndpoint]:
    rows: list[BlockEndpoint] = []
    for idx, block in enumerate(block_ids):
        jitter = ((idx % 5) - 2) * 0.001
        for endpoint in PRIMARY_ENDPOINTS:
            if mode == "equivalence":
                contrast = jitter
            elif mode == "superiority":
                contrast = 0.12 + jitter
            elif mode == "one_margin_outside":
                contrast = 0.12 if endpoint == "RCG" else jitter
            elif mode == "reverse_harm":
                contrast = -0.12 + jitter
            else:
                raise ValueError(mode)
            treatment, control = (
                (0.20 - contrast, 0.20)
                if endpoint == "SRR"
                else (0.50 + contrast, 0.50)
            )
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


def cross_report() -> dict:
    blocks = tuple(f"b{i:03d}" for i in range(200))
    plan = default_plan(blocks, DEFAULT_SCORING_CONFIG.digest)
    registry = AnalysisPlanRegistry((plan,))
    fixtures = []
    fixture_specs = [
        ("equivalence", "zero"),
        ("superiority", "zero"),
        ("one_margin_outside", "zero"),
        ("reverse_harm", "zero"),
        ("superiority", "excess"),
        ("equivalence", "zero"),
    ]
    for mode, tail_mode in fixture_specs:
        rows = fixture_rows(blocks, mode)
        tail = [
            TailPair(block, tail_mode == "excess" and idx < 10, False)
            for idx, block in enumerate(blocks)
        ]
        primary = analyze_named_estimands(rows, plan=plan, registry=registry, tail_pairs=tail)
        secondary = analyze_raw_fixture(
            [asdict(row) for row in rows],
            raw_plan(plan),
            [asdict(item) for item in tail],
            expected_plan_digest=plan.digest,
        )
        fields_match = (
            primary.verdict == secondary["verdict"]
            and primary.superiority == secondary["superiority"]
            and primary.equivalence == secondary["equivalence"]
            and primary.tail_gate_pass == secondary["tail_gate_pass"]
        )
        fixtures.append(
            {
                "mode": mode,
                "tail_mode": tail_mode,
                "primary_verdict": primary.verdict,
                "secondary_verdict": secondary["verdict"],
                "fields_match": fields_match,
            }
        )
    return {
        "fixtures": fixtures,
        "fixture_count": len(fixtures),
        "all_match": all(item["fields_match"] for item in fixtures),
    }


def build_execution_summary(
    *,
    unit: dict,
    formal: dict,
    epistemic: dict,
    sioc: dict,
    endpoint: dict,
    analysis: dict,
    mutation: dict,
    concurrency: dict,
    cross: dict,
    negative_control: dict,
) -> dict:
    checks = {
        "formal": formal.get("pass") is True,
        "epistemic": epistemic.get("pass") is True,
        "sioc": sioc.get("pass") is True,
        "endpoint": endpoint.get("pass") is True,
        "analysis": analysis.get("pass") is True,
        "unit_tests": unit.get("pass") is True,
        "mutation": mutation.get("pass") is True,
        "concurrency": concurrency.get("pass") is True,
        "cross_analysis": cross.get("all_match") is True,
        "full_execution_negative_control": negative_control.get("pass") is True,
    }
    return {
        "schema": "esther.rp001.v0.8.execution_summary.v1",
        "v0_8_tests": unit["v0_8"]["executed_count"],
        "legacy_v0_7_tests": unit["legacy_v0_7"]["executed_count"],
        "thread_concurrency_rounds": concurrency["thread_rounds"],
        "process_concurrency_rounds": concurrency["process_rounds"],
        "declared_mutants": mutation["declared_mutants"],
        "killed_mutants": mutation["counts"]["KILLED"],
        "cross_analysis_fixtures": cross["fixture_count"],
        "checks": checks,
        "pass": all(checks.values()),
        "claim_boundary": (
            "Bounded executable evidence only; no empirical continuity, consciousness, "
            "entity, production-security, or unbounded theorem claim."
        ),
    }


def main() -> int:
    current_receipt = load_json("PYTEST_V08_RECEIPT.json")
    legacy_receipt = load_json("PYTEST_LEGACY_V07_RECEIPT.json")
    unit = build_unit_test_report(current_receipt, legacy_receipt)

    mutation = load_json("MUTATION_REPORT_v0_8.json")
    concurrency = load_json("CONCURRENCY_REPORT_v0_8.json")
    formal = load_json("FORMAL_CHECK_REPORT_v0_8.json")
    epistemic = load_json("EPISTEMIC_CHECK_REPORT_v0_8.json")
    sioc = load_json("SIOC_CHECK_REPORT_v0_8.json")
    endpoint = load_json("ENDPOINT_CHECK_REPORT_v0_8.json")
    analysis = load_json("ANALYSIS_CHECK_REPORT_v0_8.json")
    negative_control = load_json("FULL_EXECUTION_NEGATIVE_CONTROL_v0_8.json")

    cross = cross_report()
    write_json("CROSS_IMPLEMENTATION_ANALYSIS_REPORT_v0_8.json", cross)
    environment = {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pytest": pytest.__version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json("ENVIRONMENT_v0_8.json", environment)
    write_json("UNIT_TEST_REPORT_v0_8.json", unit)

    summary = build_execution_summary(
        unit=unit,
        formal=formal,
        epistemic=epistemic,
        sioc=sioc,
        endpoint=endpoint,
        analysis=analysis,
        mutation=mutation,
        concurrency=concurrency,
        cross=cross,
        negative_control=negative_control,
    )
    write_json("EXECUTION_SUMMARY_v0_8.json", summary)
    commands = {
        "python_executable": sys.executable,
        "commands": [
            "PYTHONPATH=CODE python -B CODE/run_tests_v08.py --suite TESTS --pythonpath CODE --expected 190 --junit REPORTS/PYTEST_V08.xml --receipt REPORTS/PYTEST_V08_RECEIPT.json --stdout REPORTS/PYTEST_V08_STDOUT.txt --stderr REPORTS/PYTEST_V08_STDERR.txt",
            "PYTHONPATH=CODE python -B CODE/run_tests_v08.py --suite LEGACY_V07/TESTS --pythonpath LEGACY_V07/CODE --expected 177 --junit REPORTS/PYTEST_LEGACY_V07.xml --receipt REPORTS/PYTEST_LEGACY_V07_RECEIPT.json --stdout REPORTS/PYTEST_LEGACY_V07_STDOUT.txt --stderr REPORTS/PYTEST_LEGACY_V07_STDERR.txt",
            "PYTHONPATH=CODE python -B CODE/formal_v08.py > REPORTS/FORMAL_CHECK_REPORT_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/epistemic_v08.py > REPORTS/EPISTEMIC_CHECK_REPORT_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/sioc_v08.py > REPORTS/SIOC_CHECK_REPORT_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/endpoint_v08.py > REPORTS/ENDPOINT_CHECK_REPORT_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/analysis_v08.py > REPORTS/ANALYSIS_CHECK_REPORT_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/mutation_v08.py --shard 0..3 > REPORTS/MUTATION_SHARD_<n>_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/mutation_v08.py --merge REPORTS/MUTATION_SHARD_0_v0_8.json REPORTS/MUTATION_SHARD_1_v0_8.json REPORTS/MUTATION_SHARD_2_v0_8.json REPORTS/MUTATION_SHARD_3_v0_8.json > REPORTS/MUTATION_REPORT_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/concurrency_v08.py > REPORTS/CONCURRENCY_REPORT_v0_8.json",
            "PYTHONPATH=CODE python -B TOOLS/negative_control_full_execution_v08.py > REPORTS/FULL_EXECUTION_NEGATIVE_CONTROL_v0_8.json",
            "PYTHONPATH=CODE python -B CODE/finalize_reports_v08.py",
        ],
    }
    write_json("REPRODUCTION_COMMANDS_v0_8.json", commands)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
