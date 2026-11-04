[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet(
        "install",
        "db-up",
        "db-down",
        "migrate",
        "test",
        "test-db-down",
        "lint",
        "mypy",
        "format-check",
        "check"
    )]
    [string]$Task = "check"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-ProjectCommand {
    param(
        [Parameter(Mandatory)]
        [string]$Executable,
        [Parameter(Mandatory)]
        [string[]]$Arguments
    )

    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Invoke-Lint {
    Invoke-ProjectCommand poetry @("run", "ruff", "check", "--config", "pyproject.toml", "worship_bot", "tests", "migrations", "../bot_service")
}

function Invoke-FormatCheck {
    Invoke-ProjectCommand poetry @("run", "ruff", "format", "--check", "--config", "pyproject.toml", "worship_bot", "tests", "migrations", "../bot_service")
}

function Invoke-Mypy {
    Invoke-ProjectCommand poetry @("run", "mypy")
}

function Invoke-Tests {
    Invoke-ProjectCommand docker @(
        "compose", "--project-directory", "..", "-f", "../compose.yaml",
        "--profile",
        "test",
        "run",
        "--build",
        "--rm",
        "test-runner"
    )
}

switch ($Task) {
    "install" {
        Invoke-ProjectCommand poetry @("install", "--with", "dev")
    }
    "db-up" {
        Invoke-ProjectCommand docker @("compose", "--project-directory", "..", "-f", "../compose.yaml", "up", "-d", "db")
    }
    "db-down" {
        Invoke-ProjectCommand docker @("compose", "--project-directory", "..", "-f", "../compose.yaml", "down")
    }
    "migrate" {
        Invoke-ProjectCommand docker @("compose", "--project-directory", "..", "-f", "../compose.yaml", "up", "-d", "db")
        Invoke-ProjectCommand poetry @("run", "alembic", "upgrade", "head")
    }
    "test" {
        Invoke-Tests
    }
    "test-db-down" {
        Invoke-ProjectCommand docker @("compose", "--project-directory", "..", "-f", "../compose.yaml", "--profile", "test", "stop", "test-db")
    }
    "lint" {
        Invoke-Lint
    }
    "mypy" {
        Invoke-Mypy
    }
    "format-check" {
        Invoke-FormatCheck
    }
    "check" {
        Invoke-Lint
        Invoke-Mypy
        Invoke-FormatCheck
        Invoke-Tests
    }
}