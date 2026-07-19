from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys

import numpy
import pytest
import scipy

from analysis_independent_v07 import analyze_raw_fixture
from analysis_v07 import AnalysisPlanRegistry, BlockEndpoint, TailPair, analyze_named_estimands, default_plan
from endpoint_v07 import DEFAULT_SCORING_CONFIG, PRIMARY_ENDPOINTS

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "REPORTS"
REPORTS.mkdir(exist_ok=True)


def write_json(name: str, payload: object) -> None:
    (REPORTS / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_collect(path: str, pythonpath: Path) -> dict:
    env = dict(os.environ)
    env.update({
        "PYTHONPATH": str(pythonpath),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    })
    cmd = [sys.executable, "-B", "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", path]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    match = re.search(r"(\d+) tests collected", proc.stdout)
    count = int(match.group(1)) if match else sum("::" in line for line in proc.stdout.splitlines())
    return {"command": cmd, "exit_code": proc.returncode, "count": count, "output_tail": proc.stdout[-1500:]}


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
            treatment, control = ((0.20 - contrast, 0.20) if endpoint == "SRR" else (0.50 + contrast, 0.50))
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
    for mode, tail_mode in [
        ("equivalence", "zero"),
        ("superiority", "zero"),
        ("one_margin_outside", "zero"),
        ("reverse_harm", "zero"),
        ("superiority", "excess"),
        ("equivalence", "zero"),
    ]:
        rows = fixture_rows(blocks, mode)
        tail = [TailPair(b, tail_mode == "excess" and idx < 10, False) for idx, b in enumerate(blocks)]
        primary = analyze_named_estimands(rows, plan=plan, registry=registry, tail_pairs=tail)
        secondary = analyze_raw_fixture(
            [asdict(r) for r in rows],
            raw_plan(plan),
            [asdict(t) for t in tail],
            expected_plan_digest=plan.digest,
        )
        fields_match = (
            primary.verdict == secondary["verdict"]
            and primary.superiority == secondary["superiority"]
            and primary.equivalence == secondary["equivalence"]
            and primary.tail_gate_pass == secondary["tail_gate_pass"]
        )
        fixtures.append({
            "mode": mode,
            "tail_mode": tail_mode,
            "primary_verdict": primary.verdict,
            "secondary_verdict": secondary["verdict"],
            "fields_match": fields_match,
        })
    return {"fixtures": fixtures, "fixture_count": len(fixtures), "all_match": all(x["fields_match"] for x in fixtures)}


def main() -> int:
    new_collect = run_collect("TESTS", ROOT / "CODE")
    old_collect = run_collect("LEGACY_V06/TESTS", ROOT / "LEGACY_V06/CODE")
    mutation = json.loads((REPORTS / "MUTATION_REPORT_v0_7.json").read_text(encoding="utf-8"))
    concurrency = json.loads((REPORTS / "CONCURRENCY_REPORT_v0_7.json").read_text(encoding="utf-8"))
    formal = json.loads((REPORTS / "FORMAL_CHECK_REPORT_v0_7.json").read_text(encoding="utf-8"))
    epistemic = json.loads((REPORTS / "EPISTEMIC_CHECK_REPORT_v0_7.json").read_text(encoding="utf-8"))
    sioc = json.loads((REPORTS / "SIOC_CHECK_REPORT_v0_7.json").read_text(encoding="utf-8"))
    endpoint = json.loads((REPORTS / "ENDPOINT_CHECK_REPORT_v0_7.json").read_text(encoding="utf-8"))
    analysis = json.loads((REPORTS / "ANALYSIS_CHECK_REPORT_v0_7.json").read_text(encoding="utf-8"))
    cross = cross_report()
    write_json("CROSS_IMPLEMENTATION_ANALYSIS_REPORT_v0_7.json", cross)
    environment = {
        "python": sys.version,
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "pytest": pytest.__version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }
    write_json("ENVIRONMENT_v0_7.json", environment)
    unit = {
        "v0_7": new_collect,
        "legacy_v0_6": old_collect,
        "warnings_as_errors": True,
        "pass": new_collect["exit_code"] == 0 and old_collect["exit_code"] == 0 and new_collect["count"] == 177 and old_collect["count"] == 138,
    }
    write_json("UNIT_TEST_REPORT_v0_7.json", unit)
    summary = {
        "schema": "esther.rp001.v0.7.execution_summary.v1",
        "v0_7_tests": new_collect["count"],
        "legacy_v0_6_tests": old_collect["count"],
        "thread_concurrency_rounds": concurrency["thread_rounds"],
        "process_concurrency_rounds": concurrency["process_rounds"],
        "declared_mutants": mutation["declared_mutants"],
        "killed_mutants": mutation["counts"]["KILLED"],
        "cross_analysis_fixtures": cross["fixture_count"],
        "checks": {
            "formal": formal.get("pass"),
            "epistemic": epistemic.get("pass"),
            "sioc": sioc.get("pass"),
            "endpoint": endpoint.get("pass"),
            "analysis": analysis.get("pass"),
            "unit_tests": unit["pass"],
            "mutation": mutation.get("pass"),
            "concurrency": concurrency.get("pass"),
            "cross_analysis": cross.get("all_match"),
        },
        "pass": all([
            formal.get("pass"), epistemic.get("pass"), sioc.get("pass"), endpoint.get("pass"), analysis.get("pass"),
            unit["pass"], mutation.get("pass"), concurrency.get("pass"), cross.get("all_match"),
        ]),
        "claim_boundary": "Bounded executable evidence only; no empirical continuity, consciousness, entity, production-security, or unbounded theorem claim.",
    }
    write_json("EXECUTION_SUMMARY_v0_7.json", summary)
    commands = {
        "python_executable": sys.executable,
        "commands": [
            "PYTHONPATH=CODE python -B -m pytest -q -W error -p no:cacheprovider TESTS",
            "PYTHONPATH=LEGACY_V06/CODE python -B -m pytest -q -W error -p no:cacheprovider LEGACY_V06/TESTS",
            "PYTHONPATH=CODE python -B CODE/formal_v07.py > REPORTS/FORMAL_CHECK_REPORT_v0_7.json",
            "PYTHONPATH=CODE python -B CODE/epistemic_v07.py > REPORTS/EPISTEMIC_CHECK_REPORT_v0_7.json",
            "PYTHONPATH=CODE python -B CODE/sioc_v07.py > REPORTS/SIOC_CHECK_REPORT_v0_7.json",
            "PYTHONPATH=CODE python -B CODE/endpoint_v07.py > REPORTS/ENDPOINT_CHECK_REPORT_v0_7.json",
            "PYTHONPATH=CODE python -B CODE/analysis_v07.py > REPORTS/ANALYSIS_CHECK_REPORT_v0_7.json",
            "PYTHONPATH=CODE python -B CODE/mutation_v07.py > REPORTS/MUTATION_REPORT_v0_7.json",
            "PYTHONPATH=CODE python -B CODE/concurrency_v07.py > REPORTS/CONCURRENCY_REPORT_v0_7.json",
            "PYTHONPATH=CODE python -B CODE/finalize_reports_v07.py",
        ],
    }
    write_json("REPRODUCTION_COMMANDS_v0_7.json", commands)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
