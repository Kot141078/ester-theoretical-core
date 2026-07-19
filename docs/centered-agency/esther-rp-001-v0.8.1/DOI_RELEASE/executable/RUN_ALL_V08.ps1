param([string]$PythonExe = "python")
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"

function Run-Python {
  param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string[]]$PyArgs
  )
  $env:PYTHONPATH = $PythonPath
  & $PythonExe -B @PyArgs
  $Code = $LASTEXITCODE
  if ($Code -ne 0) {
    throw ("Python command failed with exit code {0}: {1}" -f $Code, ($PyArgs -join ' '))
  }
}

function Run-PythonToFile {
  param(
    [Parameter(Mandatory = $true)][string]$PythonPath,
    [Parameter(Mandatory = $true)][string[]]$PyArgs,
    [Parameter(Mandatory = $true)][string]$OutputPath
  )
  $env:PYTHONPATH = $PythonPath
  $Output = & $PythonExe -B @PyArgs
  $Code = $LASTEXITCODE
  $Output | Set-Content -Encoding utf8 -LiteralPath $OutputPath
  if ($Code -ne 0) {
    throw ("Python command failed with exit code {0}: {1}" -f $Code, ($PyArgs -join ' '))
  }
}

$CodePath = Join-Path $Root "CODE"
$LegacyPath = Join-Path $Root "LEGACY_V07\CODE"

Run-Python -PythonPath $CodePath -PyArgs @(
  "CODE/run_tests_v08.py",
  "--suite", "TESTS",
  "--pythonpath", "CODE",
  "--expected", "190",
  "--junit", "REPORTS/PYTEST_V08.xml",
  "--receipt", "REPORTS/PYTEST_V08_RECEIPT.json",
  "--stdout", "REPORTS/PYTEST_V08_STDOUT.txt",
  "--stderr", "REPORTS/PYTEST_V08_STDERR.txt"
)

Run-Python -PythonPath $CodePath -PyArgs @(
  "CODE/run_tests_v08.py",
  "--suite", "LEGACY_V07/TESTS",
  "--pythonpath", "LEGACY_V07/CODE",
  "--expected", "177",
  "--junit", "REPORTS/PYTEST_LEGACY_V07.xml",
  "--receipt", "REPORTS/PYTEST_LEGACY_V07_RECEIPT.json",
  "--stdout", "REPORTS/PYTEST_LEGACY_V07_STDOUT.txt",
  "--stderr", "REPORTS/PYTEST_LEGACY_V07_STDERR.txt"
)

Run-PythonToFile -PythonPath $CodePath -PyArgs @("CODE/formal_v08.py") -OutputPath "REPORTS/FORMAL_CHECK_REPORT_v0_8.json"
Run-PythonToFile -PythonPath $CodePath -PyArgs @("CODE/epistemic_v08.py") -OutputPath "REPORTS/EPISTEMIC_CHECK_REPORT_v0_8.json"
Run-PythonToFile -PythonPath $CodePath -PyArgs @("CODE/sioc_v08.py") -OutputPath "REPORTS/SIOC_CHECK_REPORT_v0_8.json"
Run-PythonToFile -PythonPath $CodePath -PyArgs @("CODE/endpoint_v08.py") -OutputPath "REPORTS/ENDPOINT_CHECK_REPORT_v0_8.json"
Run-PythonToFile -PythonPath $CodePath -PyArgs @("CODE/analysis_v08.py") -OutputPath "REPORTS/ANALYSIS_CHECK_REPORT_v0_8.json"
foreach ($Shard in 0..3) {
  Run-PythonToFile -PythonPath $CodePath `
    -PyArgs @("CODE/mutation_v08.py", "--shard", "$Shard") `
    -OutputPath "REPORTS/MUTATION_SHARD_${Shard}_v0_8.json"
}
Run-PythonToFile -PythonPath $CodePath -PyArgs @(
  "CODE/mutation_v08.py", "--merge",
  "REPORTS/MUTATION_SHARD_0_v0_8.json",
  "REPORTS/MUTATION_SHARD_1_v0_8.json",
  "REPORTS/MUTATION_SHARD_2_v0_8.json",
  "REPORTS/MUTATION_SHARD_3_v0_8.json"
) -OutputPath "REPORTS/MUTATION_REPORT_v0_8.json"
Run-PythonToFile -PythonPath $CodePath -PyArgs @("CODE/concurrency_v08.py") -OutputPath "REPORTS/CONCURRENCY_REPORT_v0_8.json"
Run-PythonToFile -PythonPath $CodePath -PyArgs @("TOOLS/negative_control_full_execution_v08.py") -OutputPath "REPORTS/FULL_EXECUTION_NEGATIVE_CONTROL_v0_8.json"
Run-PythonToFile -PythonPath $CodePath -PyArgs @("CODE/finalize_reports_v08.py") -OutputPath "REPORTS/FINALIZER_STDOUT_v0_8.json"

$Summary = Get-Content -Raw -LiteralPath "REPORTS/EXECUTION_SUMMARY_v0_8.json" | ConvertFrom-Json
if (-not $Summary.pass) {
  throw "Execution summary reports failure"
}
Get-Content -Raw -LiteralPath "REPORTS/EXECUTION_SUMMARY_v0_8.json"
