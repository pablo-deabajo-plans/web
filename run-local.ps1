param(
    [ValidateSet("setup", "pipeline", "api", "test", "all")]
    [string]$Command = "all",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [string[]]$PytestArgs = @()
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$RequirementsFile = Join-Path $RepoRoot "requirements.local.txt"

function Get-BasePython {
    $candidates = @(
        @{ Name = "py"; Args = @("-3.11") },
        @{ Name = "python"; Args = @() },
        @{ Name = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        $command = Get-Command $candidate.Name -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            return $candidate
        }
    }

    throw "Python 3.11+ was not found. Install Python or create .venv manually."
}

function Ensure-Venv {
    if (-not (Test-Path $VenvPython)) {
        $basePython = Get-BasePython
        & $basePython.Name @($basePython.Args + @("-m", "venv", ".venv")) | Out-Null
    }
}

function Ensure-Dependencies {
    Ensure-Venv
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r $RequirementsFile
}

Push-Location $RepoRoot
try {
    Ensure-Dependencies

    switch ($Command) {
        "setup" {
            & $VenvPython -m backend.tools.local_runner setup
        }
        "pipeline" {
            & $VenvPython -m backend.tools.local_runner pipeline
        }
        "api" {
            & $VenvPython -m backend.tools.local_runner api --host $Host --port $Port
        }
        "test" {
            & $VenvPython -m backend.tools.local_runner test @PytestArgs
        }
        "all" {
            & $VenvPython -m backend.tools.local_runner all --host $Host --port $Port
        }
    }
}
finally {
    Pop-Location
}
