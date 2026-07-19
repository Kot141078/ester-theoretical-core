from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from common_v08 import file_sha256, sha256_digest


def parse_junit(path: Path) -> dict[str, int]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    if not suites:
        suites = list(root.iter("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for suite in suites:
        for key in totals:
            totals[key] += int(suite.attrib.get(key, "0"))
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    totals["executed"] = totals["tests"]
    return totals


def run_pytest_suite(
    *,
    package_root: Path,
    suite: str,
    pythonpath: Path,
    expected_tests: int,
    junit_path: Path,
    receipt_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> dict:
    package_root = package_root.resolve()
    pythonpath = pythonpath.resolve()
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env.update(
        {
            "PYTHONPATH": str(pythonpath),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    command = [
        sys.executable,
        "-B",
        "-m",
        "pytest",
        "-q",
        "-W",
        "error",
        "-p",
        "no:cacheprovider",
        f"--junitxml={junit_path}",
        suite,
    ]
    proc = subprocess.run(
        command,
        cwd=package_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")

    counts = parse_junit(junit_path) if junit_path.exists() else {
        "tests": 0,
        "failures": 0,
        "errors": 1,
        "skipped": 0,
        "passed": 0,
        "executed": 0,
    }
    passed = (
        proc.returncode == 0
        and counts["tests"] == expected_tests
        and counts["executed"] == expected_tests
        and counts["passed"] == expected_tests
        and counts["failures"] == 0
        and counts["errors"] == 0
        and counts["skipped"] == 0
    )
    payload = {
        "schema": "esther.rp001.v0.8.pytest_receipt.v1",
        "suite": suite,
        "python_executable": sys.executable,
        "pythonpath": str(pythonpath),
        "command": command,
        "full_pytest_exit_code": proc.returncode,
        "expected_tests": expected_tests,
        "collected_count": counts["tests"],
        "executed_count": counts["executed"],
        "passed_count": counts["passed"],
        "failed_count": counts["failures"],
        "error_count": counts["errors"],
        "skipped_count": counts["skipped"],
        "execution_mode": "full_pytest_junit",
        "junit_path": str(junit_path.resolve().relative_to(package_root)),
        "junit_sha256": file_sha256(str(junit_path)) if junit_path.exists() else None,
        "stdout_path": str(stdout_path.resolve().relative_to(package_root)),
        "stdout_sha256": file_sha256(str(stdout_path)),
        "stderr_path": str(stderr_path.resolve().relative_to(package_root)),
        "stderr_sha256": file_sha256(str(stderr_path)),
        "stdout_tail": proc.stdout[-1500:],
        "stderr_tail": proc.stderr[-1500:],
        "pass": passed,
    }
    payload["receipt_digest"] = sha256_digest(payload)
    receipt_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--pythonpath", required=True)
    parser.add_argument("--expected", type=int, required=True)
    parser.add_argument("--junit", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--stdout", required=True)
    parser.add_argument("--stderr", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    result = run_pytest_suite(
        package_root=root,
        suite=args.suite,
        pythonpath=(root / args.pythonpath),
        expected_tests=args.expected,
        junit_path=(root / args.junit),
        receipt_path=(root / args.receipt),
        stdout_path=(root / args.stdout),
        stderr_path=(root / args.stderr),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
