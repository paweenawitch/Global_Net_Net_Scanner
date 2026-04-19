#!/usr/bin/env pwsh
# scripts/check.ps1
# Runs fast checks like architecture dependency enforcement tests.

$ErrorActionPreference = "Stop"

echo "Running Architecture Enforcement Tests..."
# Use python -m to run pytest to ensure it runs inside the existing virtual environment.
python -m pytest tests/

if ($LASTEXITCODE -eq 0) {
    echo "All checks passed!"
} else {
    echo "Checks failed. See test output."
    exit 1
}
