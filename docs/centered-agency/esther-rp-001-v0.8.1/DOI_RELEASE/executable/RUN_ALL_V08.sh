#!/usr/bin/env bash
set -euo pipefail
PYTHON_BIN="${PYTHON_BIN:-python}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"
export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export PYTHONPATH="$ROOT/CODE"

"$PYTHON_BIN" -B CODE/run_tests_v08.py \
  --suite TESTS --pythonpath CODE --expected 190 \
  --junit REPORTS/PYTEST_V08.xml \
  --receipt REPORTS/PYTEST_V08_RECEIPT.json \
  --stdout REPORTS/PYTEST_V08_STDOUT.txt \
  --stderr REPORTS/PYTEST_V08_STDERR.txt

"$PYTHON_BIN" -B CODE/run_tests_v08.py \
  --suite LEGACY_V07/TESTS --pythonpath LEGACY_V07/CODE --expected 177 \
  --junit REPORTS/PYTEST_LEGACY_V07.xml \
  --receipt REPORTS/PYTEST_LEGACY_V07_RECEIPT.json \
  --stdout REPORTS/PYTEST_LEGACY_V07_STDOUT.txt \
  --stderr REPORTS/PYTEST_LEGACY_V07_STDERR.txt

"$PYTHON_BIN" -B CODE/formal_v08.py > REPORTS/FORMAL_CHECK_REPORT_v0_8.json
"$PYTHON_BIN" -B CODE/epistemic_v08.py > REPORTS/EPISTEMIC_CHECK_REPORT_v0_8.json
"$PYTHON_BIN" -B CODE/sioc_v08.py > REPORTS/SIOC_CHECK_REPORT_v0_8.json
"$PYTHON_BIN" -B CODE/endpoint_v08.py > REPORTS/ENDPOINT_CHECK_REPORT_v0_8.json
"$PYTHON_BIN" -B CODE/analysis_v08.py > REPORTS/ANALYSIS_CHECK_REPORT_v0_8.json
for shard in 0 1 2 3; do
  "$PYTHON_BIN" -B CODE/mutation_v08.py --shard "$shard" > "REPORTS/MUTATION_SHARD_${shard}_v0_8.json"
done
"$PYTHON_BIN" -B CODE/mutation_v08.py --merge \
  REPORTS/MUTATION_SHARD_0_v0_8.json \
  REPORTS/MUTATION_SHARD_1_v0_8.json \
  REPORTS/MUTATION_SHARD_2_v0_8.json \
  REPORTS/MUTATION_SHARD_3_v0_8.json \
  > REPORTS/MUTATION_REPORT_v0_8.json
"$PYTHON_BIN" -B CODE/concurrency_v08.py > REPORTS/CONCURRENCY_REPORT_v0_8.json
"$PYTHON_BIN" -B TOOLS/negative_control_full_execution_v08.py > REPORTS/FULL_EXECUTION_NEGATIVE_CONTROL_v0_8.json
"$PYTHON_BIN" -B CODE/finalize_reports_v08.py > REPORTS/FINALIZER_STDOUT_v0_8.json
