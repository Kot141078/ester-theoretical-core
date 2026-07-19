param([string]$PythonExe = "C:\Python310\python.exe")
$ErrorActionPreference = "Stop"
$SourceRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$WorkRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("esther-v08-windows-runner-" + [guid]::NewGuid().ToString("N"))
$CleanRoot = Join-Path $WorkRoot "clean"
$FailRoot = Join-Path $WorkRoot "failing"

function Copy-Package([string]$Destination) {
  New-Item -ItemType Directory -Force -Path $Destination | Out-Null
  Get-ChildItem -LiteralPath $SourceRoot -Force | Where-Object {
    $_.Name -notin @("REPORTS", "__pycache__", ".pytest_cache")
  } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $Destination -Recurse -Force
  }
  New-Item -ItemType Directory -Force -Path (Join-Path $Destination "REPORTS") | Out-Null
}

try {
  Copy-Package $CleanRoot
  $cleanLog = Join-Path $WorkRoot "clean.log"
  & (Join-Path $CleanRoot "RUN_ALL_V08.ps1") -PythonExe $PythonExe *>&1 | Tee-Object -FilePath $cleanLog | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "clean runner returned nonzero" }
  $cleanText = Get-Content -Raw -LiteralPath $cleanLog
  if ($cleanText -match ">>>") { throw "clean runner entered Python REPL" }
  $cleanSummary = Get-Content -Raw -LiteralPath (Join-Path $CleanRoot "REPORTS\EXECUTION_SUMMARY_v0_8.json") | ConvertFrom-Json
  if (-not $cleanSummary.pass) { throw "clean execution summary is not PASS" }
  if ($cleanSummary.v0_8_tests -ne 190 -or $cleanSummary.legacy_v0_7_tests -ne 177) {
    throw "clean runner test counts mismatch"
  }

  Copy-Package $FailRoot
  $negativeTestPath = Join-Path $FailRoot "TESTS\test_reproducibility_v08.py"
  $negativeTestText = Get-Content -Raw -LiteralPath $negativeTestPath
  $negativeNeedle = "def test_parse_junit_clean_suite(tmp_path):"
  if (-not $negativeTestText.Contains($negativeNeedle)) {
    throw "negative-control target test was not found"
  }
  $negativeReplacement = $negativeNeedle + "`n    assert False, `"V08_WINDOWS_NEGATIVE_CONTROL`""
  $negativeTestText = $negativeTestText.Replace($negativeNeedle, $negativeReplacement)
  Set-Content -LiteralPath $negativeTestPath -Encoding utf8 -Value $negativeTestText
  $negativeFailed = $false
  try {
    & (Join-Path $FailRoot "RUN_ALL_V08.ps1") -PythonExe $PythonExe *> (Join-Path $WorkRoot "failing.log")
  } catch {
    $negativeFailed = $true
  }
  if (-not $negativeFailed) { throw "failing-but-collectable test did not make runner fail" }

  [pscustomobject]@{
    schema = "esther.rp001.v0.8.windows_runner_verification.v1"
    clean_runner = "PASS"
    clean_v0_8_tests = $cleanSummary.v0_8_tests
    clean_legacy_v0_7_tests = $cleanSummary.legacy_v0_7_tests
    repl_prompt_observed = $false
    negative_control = "PASS_NONZERO"
  } | ConvertTo-Json -Depth 4
} finally {
  Remove-Item -LiteralPath $WorkRoot -Recurse -Force -ErrorAction SilentlyContinue
}
