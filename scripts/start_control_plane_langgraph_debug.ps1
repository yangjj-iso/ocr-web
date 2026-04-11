[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$javaControlPlaneDir = Join-Path $projectRoot "java-control-plane"
$jarPath = Join-Path $javaControlPlaneDir "target\java-control-plane-0.0.1-SNAPSHOT.jar"
$defaultJava = "C:\Program Files\Java\jdk-21\bin\java.exe"

function Resolve-JavaExecutable {
    if (Test-Path $defaultJava) {
        return $defaultJava
    }

    $javaFromPath = Get-Command java -ErrorAction SilentlyContinue
    if ($null -ne $javaFromPath -and $javaFromPath.Source) {
        return $javaFromPath.Source
    }

    throw "Java executable not found. Install JDK 21 or add java.exe to PATH."
}

if (-not (Test-Path $jarPath)) {
    throw "Control plane jar not found: $jarPath"
}

$javaExe = Resolve-JavaExecutable

$env:ENABLE_HIERARCHICAL_AGENT = "true"
Set-Location $javaControlPlaneDir

Write-Host "Starting control plane in LangGraph debug mode..."
Write-Host "ENABLE_HIERARCHICAL_AGENT=true"
Write-Host "Jar: $jarPath"
Write-Host "Java: $javaExe"
Write-Host "Health: http://127.0.0.1:8080/api/health"

& $javaExe -jar $jarPath
