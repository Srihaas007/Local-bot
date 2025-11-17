# Quickstart for Local Agent on Windows (PowerShell)
# Usage: Right-click -> Run with PowerShell, or execute in a PowerShell terminal.

$ErrorActionPreference = 'Stop'

# 1) Create venv if missing
if (!(Test-Path -Path ".\.venv")) {
  Write-Host "Creating venv..."
  python -m venv .venv
}

# 2) Activate venv
. .\.venv\Scripts\Activate.ps1

# 3) Install requirements
Write-Host "Installing requirements..."
pip install --upgrade pip
pip install -r requirements.txt

# 4) Start server
Write-Host "Starting server on http://127.0.0.1:8000 ..."
python -m uvicorn src.local_agent.web.server:app --host 127.0.0.1 --port 8000
