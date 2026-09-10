# scripts/ci.ps1 — pipeline local equivalente ao GitHub Actions CI
# Executa: lint -> test -> build-validate
param([switch]$SkipInstall)
$ErrorActionPreference = "Stop"

Push-Location "$PSScriptRoot\.."
try {
  if (-not $SkipInstall) {
    Write-Host "==> [1/4] install" -ForegroundColor Cyan
    python -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) { throw "install failed" }
  }

  Write-Host "==> [2/4] lint (ruff)" -ForegroundColor Cyan
  python -m ruff check .
  $lintExit = $LASTEXITCODE
  # ruff: avisos não devem quebrar o CI; só erros fatais (2)
  if ($lintExit -ge 2) { throw "lint failed com exit=$lintExit" }

  Write-Host "==> [3/4] pytest" -ForegroundColor Cyan
  python -m pytest --cov=src --cov-report=xml:coverage.xml --cov-report=html:htmlcov --junitxml=test-results.xml
  if ($LASTEXITCODE -ne 0) { throw "pytest failed" }

  Write-Host "==> [4/4] build-validate" -ForegroundColor Cyan
  python -m compileall -q src tests
  python -c "from src.config import settings; print('smoke ok:', type(settings).__name__)"
  if ($LASTEXITCODE -ne 0) { throw "build-validate failed" }

  Write-Host "==> CI passou :)" -ForegroundColor Green
} finally {
  Pop-Location
}
