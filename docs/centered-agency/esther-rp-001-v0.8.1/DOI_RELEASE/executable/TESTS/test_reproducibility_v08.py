from __future__ import annotations

import hashlib
import json
from pathlib import Path

from common_v08 import sha256_digest
from finalize_reports_v08 import (
    CURRENT_EXPECTED_TESTS,
    LEGACY_EXPECTED_TESTS,
    build_execution_summary,
    build_unit_test_report,
)
from run_tests_v08 import parse_junit, run_pytest_suite


ROOT = Path(__file__).resolve().parents[1]


def _raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_receipt(
    tmp_path: Path,
    *,
    suite: str,
    expected: int,
    failures: int = 0,
    errors: int = 0,
    skipped: int = 0,
    exit_code: int | None = None,
):
    stem = suite.replace("/", "_").replace("\\", "_")
    junit = tmp_path / f"{stem}.xml"
    stdout = tmp_path / f"{stem}.stdout.txt"
    stderr = tmp_path / f"{stem}.stderr.txt"
    junit.write_text(
        f'<testsuites><testsuite tests="{expected}" failures="{failures}" errors="{errors}" skipped="{skipped}"/></testsuites>',
        encoding="utf-8",
    )
    stdout.write_text("pytest evidence\n", encoding="utf-8")
    stderr.write_text("", encoding="utf-8")
    passed = expected - failures - errors - skipped
    payload = {
        "schema": "esther.rp001.v0.8.pytest_receipt.v1",
        "suite": suite,
        "python_executable": "python",
        "pythonpath": "CODE",
        "command": ["python", "-m", "pytest"],
        "full_pytest_exit_code": (0 if failures == errors == 0 else 1) if exit_code is None else exit_code,
        "expected_tests": expected,
        "collected_count": expected,
        "executed_count": expected,
        "passed_count": passed,
        "failed_count": failures,
        "error_count": errors,
        "skipped_count": skipped,
        "execution_mode": "full_pytest_junit",
        "junit_path": str(junit),
        "junit_sha256": _raw_sha256(junit),
        "stdout_path": str(stdout),
        "stdout_sha256": _raw_sha256(stdout),
        "stderr_path": str(stderr),
        "stderr_sha256": _raw_sha256(stderr),
        "stdout_tail": "",
        "stderr_tail": "",
        "pass": failures == errors == skipped == 0 and (exit_code in (None, 0)),
    }
    payload["receipt_digest"] = sha256_digest(payload)
    return payload


def test_parse_junit_clean_suite(tmp_path):
    path = tmp_path / "clean.xml"
    path.write_text('<testsuites><testsuite tests="3" failures="0" errors="0" skipped="0"/></testsuites>', encoding="utf-8")
    assert parse_junit(path) == {"tests": 3, "failures": 0, "errors": 0, "skipped": 0, "passed": 3, "executed": 3}


def test_parse_junit_failure_is_not_passed(tmp_path):
    path = tmp_path / "failed.xml"
    path.write_text('<testsuites><testsuite tests="3" failures="1" errors="0" skipped="0"/></testsuites>', encoding="utf-8")
    assert parse_junit(path) == {"tests": 3, "failures": 1, "errors": 0, "skipped": 0, "passed": 2, "executed": 3}

    suite = tmp_path / "failing_suite"
    suite.mkdir()
    (suite / "test_failure.py").write_text(
        'def test_failing_but_collectable():\n    assert False, "V08_NEGATIVE_CONTROL"\n',
        encoding="utf-8",
    )
    receipt = run_pytest_suite(
        package_root=tmp_path,
        suite="failing_suite",
        pythonpath=ROOT / "CODE",
        expected_tests=1,
        junit_path=tmp_path / "negative.xml",
        receipt_path=tmp_path / "negative_receipt.json",
        stdout_path=tmp_path / "negative_stdout.txt",
        stderr_path=tmp_path / "negative_stderr.txt",
    )
    assert receipt["full_pytest_exit_code"] != 0
    assert receipt["collected_count"] == 1
    assert receipt["executed_count"] == 1
    assert receipt["failed_count"] == 1
    assert not receipt["pass"]


def test_unit_report_requires_full_clean_execution(tmp_path):
    report = build_unit_test_report(
        make_receipt(tmp_path, suite="TESTS", expected=CURRENT_EXPECTED_TESTS),
        make_receipt(tmp_path, suite="LEGACY_V07/TESTS", expected=LEGACY_EXPECTED_TESTS),
        artifact_root=tmp_path,
    )
    assert report["execution_mode"] == "full_pytest_junit_receipts"
    assert report["v0_8"]["verified_pass"]
    assert report["legacy_v0_7"]["verified_pass"]
    assert report["v0_8"]["artifact_evidence_valid"]
    assert report["pass"]

    Path(report["v0_8"]["stdout_path"]).write_text("tampered\n", encoding="utf-8")
    tampered = build_unit_test_report(
        json.loads(json.dumps({k: v for k, v in report["v0_8"].items() if k not in {"receipt_digest_valid", "contract_fields_valid", "execution_evidence_valid", "artifact_evidence", "artifact_evidence_valid", "verified_pass"}})),
        make_receipt(tmp_path, suite="LEGACY_V07/TESTS", expected=LEGACY_EXPECTED_TESTS),
        artifact_root=tmp_path,
    )
    assert not tampered["v0_8"]["artifact_evidence_valid"]
    assert not tampered["pass"]


def test_unit_report_rejects_failing_but_collectable_suite(tmp_path):
    report = build_unit_test_report(
        make_receipt(tmp_path, suite="TESTS", expected=CURRENT_EXPECTED_TESTS, failures=1),
        make_receipt(tmp_path, suite="LEGACY_V07/TESTS", expected=LEGACY_EXPECTED_TESTS),
        artifact_root=tmp_path,
    )
    assert report["v0_8"]["collected_count"] == CURRENT_EXPECTED_TESTS
    assert report["v0_8"]["executed_count"] == CURRENT_EXPECTED_TESTS
    assert not report["v0_8"]["verified_pass"]
    assert not report["pass"]


def test_execution_summary_cannot_override_failed_unit_evidence(tmp_path):
    unit = build_unit_test_report(
        make_receipt(tmp_path, suite="TESTS", expected=CURRENT_EXPECTED_TESTS, failures=1),
        make_receipt(tmp_path, suite="LEGACY_V07/TESTS", expected=LEGACY_EXPECTED_TESTS),
        artifact_root=tmp_path,
    )
    summary = build_execution_summary(
        unit=unit,
        formal={"pass": True},
        epistemic={"pass": True},
        sioc={"pass": True},
        endpoint={"pass": True},
        analysis={"pass": True},
        mutation={"pass": True, "declared_mutants": 1, "counts": {"KILLED": 1}},
        concurrency={"pass": True, "thread_rounds": 1, "process_rounds": 1},
        cross={"all_match": True, "fixture_count": 1},
        negative_control={"pass": True},
    )
    assert not summary["checks"]["unit_tests"]
    assert not summary["pass"]


def test_windows_runner_uses_named_pyargs_not_automatic_args():
    text = (ROOT / "RUN_ALL_V08.ps1").read_text(encoding="utf-8")
    assert "[string[]]$PyArgs" in text
    assert "[string[]]$Args" not in text
    assert "-PyArgs" in text
    assert "PYTEST_V08_RECEIPT.json" in text
    assert "PYTEST_LEGACY_V07_RECEIPT.json" in text
    verifier = (ROOT / "TOOLS" / "VERIFY_WINDOWS_RUNNER_V08.ps1").read_text(encoding="utf-8")
    assert "V08_WINDOWS_NEGATIVE_CONTROL" in verifier
    assert "repl_prompt_observed" in verifier
    assert "failing-but-collectable" in verifier


def test_finalizer_never_uses_collect_only_as_pass_evidence():
    text = (ROOT / "CODE" / "finalize_reports_v08.py").read_text(encoding="utf-8")
    assert "--collect-only" not in text
    assert "PYTEST_V08_RECEIPT.json" in text
    assert "full_pytest_exit_code" in text
    assert "executed_count" in text
