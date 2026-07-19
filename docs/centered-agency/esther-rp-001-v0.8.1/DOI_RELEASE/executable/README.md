# Executable review surface

This directory is copied from the exact `v0.8.1` blind-review packet.

## Windows

```powershell
.\RUN_ALL_V08.ps1 -PythonExe 'C:\Python310\python.exe'
.\TOOLS\VERIFY_WINDOWS_RUNNER_V08.ps1 -PythonExe 'C:\Python310\python.exe'
```

## Linux

```bash
bash RUN_ALL_V08.sh
```

Expected bounded counts:

```text
190 v0.8 tests
177 legacy v0.7 tests
100 thread rounds
20 process rounds
16 source mutants
6 cross-analysis fixtures
```

Verify `SHA256SUMS.txt` before running. Generated report changes are expected
inside `REPORTS/`; frozen source and manuscript files must not change.
