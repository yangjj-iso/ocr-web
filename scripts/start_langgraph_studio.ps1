[CmdletBinding()]
param(
    [int]$Port = 8123,
    [switch]$NoBrowser
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$script:LangGraphConfigPath = Join-Path $script:ProjectRoot "langgraph.json"
$script:VenvPython = Join-Path $script:ProjectRoot ".venv\Scripts\python.exe"
$script:LangGraphExe = Join-Path $script:ProjectRoot ".venv\Scripts\langgraph.exe"

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host ("== {0} ==" -f $Title)
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw ("{0} not found: {1}" -f $Label, $Path)
    }
}

function Get-PortListeners {
    param([int]$LocalPort)

    $connections = Get-NetTCPConnection -State Listen -LocalPort $LocalPort -ErrorAction SilentlyContinue
    if ($null -eq $connections) {
        return @()
    }

    $rows = @()
    foreach ($connection in @($connections)) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        $rows += [PSCustomObject]@{
            LocalPort = $LocalPort
            ProcessId = $connection.OwningProcess
            ProcessName = if ($process) { $process.ProcessName } else { "<unknown>" }
        }
    }
    return $rows
}

function Set-Utf8Console {
    try {
        chcp 65001 | Out-Null
    } catch {
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [Console]::InputEncoding = $utf8NoBom
    [Console]::OutputEncoding = $utf8NoBom
    $global:OutputEncoding = $utf8NoBom
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUTF8 = "1"
}

Write-Section "LangGraph Studio"
Assert-PathExists -Path $script:LangGraphConfigPath -Label "LangGraph config"
Assert-PathExists -Path $script:VenvPython -Label "Project virtualenv python"
Assert-PathExists -Path $script:LangGraphExe -Label "LangGraph CLI"

$listeners = @(Get-PortListeners -LocalPort $Port)
if ($listeners.Count -gt 0) {
    $summary = ($listeners | ForEach-Object { "{0} (PID {1})" -f $_.ProcessName, $_.ProcessId }) -join ", "
    throw ("Port {0} is already in use: {1}" -f $Port, $summary)
}

Set-Utf8Console
Set-Location $script:ProjectRoot

$env:LANGGRAPH_CHECKPOINTER_BACKEND = "memory"
$env:LANGGRAPH_CHECKPOINTER_DSN = ""
$env:LANGGRAPH_CHECKPOINTER_REDIS_URL = ""
$env:LANGGRAPH_HITL_ENABLED = "true"
$env:LANGCHAIN_TRACING_V2 = "false"

$args = @("dev", "--port", "$Port")
if ($NoBrowser) {
    $args += "--no-browser"
}

Write-Host ("Project root : {0}" -f $script:ProjectRoot)
Write-Host ("Config file  : {0}" -f $script:LangGraphConfigPath)
Write-Host ("CLI          : {0}" -f $script:LangGraphExe)
Write-Host ("Base URL     : http://127.0.0.1:{0}" -f $Port)
Write-Host "Graphs       : batch_supervisor, page_agent"
Write-Host ""
Write-Host "Available endpoints"
Write-Host ("- http://127.0.0.1:{0}/health/live" -f $Port)
Write-Host ("- http://127.0.0.1:{0}/studio/info" -f $Port)
Write-Host ("- http://127.0.0.1:{0}/studio/flow" -f $Port)

& $script:LangGraphExe @args
if ($LASTEXITCODE -ne 0) {
    throw ("LangGraph Studio exited with code {0}." -f $LASTEXITCODE)
}
