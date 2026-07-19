from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="esther-v08-negative-control-") as td:
        copy = Path(td) / "candidate"
        shutil.copytree(
            ROOT,
            copy,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "REVIEW"),
        )
        test_file = copy / "TESTS" / "test_reproducibility_v08.py"
        text = test_file.read_text(encoding="utf-8")
        marker = "def test_finalizer_never_uses_collect_only_as_pass_evidence():\n"
        if marker not in text:
            raise RuntimeError("negative-control sentinel test was not found")
        text = text.replace(
            marker,
            marker + '    assert False, "V08_NEGATIVE_CONTROL_FAIL"\n',
            1,
        )
        test_file.write_text(text, encoding="utf-8")

        reports = copy / "REPORTS"
        reports.mkdir(exist_ok=True)
        env = dict(os.environ)
        env.update({
            "PYTHONPATH": str(copy / "CODE"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        })
        current = run([
            sys.executable, "-B", "CODE/run_tests_v08.py",
            "--suite", "TESTS", "--pythonpath", "CODE", "--expected", "190",
            "--junit", "REPORTS/PYTEST_V08.xml",
            "--receipt", "REPORTS/PYTEST_V08_RECEIPT.json",
            "--stdout", "REPORTS/PYTEST_V08_STDOUT.txt",
            "--stderr", "REPORTS/PYTEST_V08_STDERR.txt",
        ], copy, env)
        legacy = run([
            sys.executable, "-B", "CODE/run_tests_v08.py",
            "--suite", "LEGACY_V07/TESTS", "--pythonpath", "LEGACY_V07/CODE", "--expected", "177",
            "--junit", "REPORTS/PYTEST_LEGACY_V07.xml",
            "--receipt", "REPORTS/PYTEST_LEGACY_V07_RECEIPT.json",
            "--stdout", "REPORTS/PYTEST_LEGACY_V07_STDOUT.txt",
            "--stderr", "REPORTS/PYTEST_LEGACY_V07_STDERR.txt",
        ], copy, env)

        # The finalizer needs all non-test reports. These are neutral PASS stubs;
        # the negative control is solely about whether failed full-test evidence
        # can be misreported as a global PASS.
        for name in (
            "FORMAL_CHECK_REPORT_v0_8.json",
            "EPISTEMIC_CHECK_REPORT_v0_8.json",
            "SIOC_CHECK_REPORT_v0_8.json",
            "ENDPOINT_CHECK_REPORT_v0_8.json",
            "ANALYSIS_CHECK_REPORT_v0_8.json",
        ):
            write_json(reports / name, {"pass": True})
        write_json(
            reports / "MUTATION_REPORT_v0_8.json",
            {"pass": True, "declared_mutants": 16, "counts": {"KILLED": 16, "SURVIVED": 0, "ERROR": 0}},
        )
        write_json(
            reports / "CONCURRENCY_REPORT_v0_8.json",
            {"pass": True, "thread_rounds": 100, "process_rounds": 20},
        )
        # Avoid recursive dependence while this disposable finalizer is itself
        # verifying failed-test handling.
        write_json(reports / "FULL_EXECUTION_NEGATIVE_CONTROL_v0_8.json", {"pass": True, "nested_stub": True})

        finalizer = run([sys.executable, "-B", "CODE/finalize_reports_v08.py"], copy, env)

        current_receipt = json.loads((reports / "PYTEST_V08_RECEIPT.json").read_text(encoding="utf-8"))
        unit = json.loads((reports / "UNIT_TEST_REPORT_v0_8.json").read_text(encoding="utf-8"))
        summary = json.loads((reports / "EXECUTION_SUMMARY_v0_8.json").read_text(encoding="utf-8"))
        payload = {
            "schema": "esther.rp001.v0.8.full_execution_negative_control.v1",
            "injected_marker": "V08_NEGATIVE_CONTROL_FAIL",
            "current_runner_exit_code": current.returncode,
            "legacy_runner_exit_code": legacy.returncode,
            "finalizer_exit_code": finalizer.returncode,
            "current_receipt": {
                "collected_count": current_receipt["collected_count"],
                "executed_count": current_receipt["executed_count"],
                "passed_count": current_receipt["passed_count"],
                "failed_count": current_receipt["failed_count"],
                "pass": current_receipt["pass"],
            },
            "unit_report_pass": unit["pass"],
            "execution_summary_unit_tests": summary["checks"]["unit_tests"],
            "execution_summary_pass": summary["pass"],
            "pass": (
                current.returncode != 0
                and legacy.returncode == 0
                and finalizer.returncode != 0
                and current_receipt["collected_count"] == 190
                and current_receipt["executed_count"] == 190
                and current_receipt["failed_count"] == 1
                and current_receipt["pass"] is False
                and unit["pass"] is False
                and summary["checks"]["unit_tests"] is False
                and summary["pass"] is False
            ),
            "stdout_tail": current.stdout[-1000:],
            "stderr_tail": current.stderr[-1000:],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
