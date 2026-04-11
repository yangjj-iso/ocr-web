[CmdletBinding()]
param(
    [ValidateSet("Validate", "Status", "Up", "Down", "Restart")]
    [string]$Action = "Status",
    [switch]$StopLocalServices,
    [switch]$DestroyData,
    [int]$DockerStartupTimeoutSeconds = 120
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ComposePath = Join-Path $ProjectRoot "compose.middleware.yaml"
$EnvPath = Join-Path $ProjectRoot ".env.docker"
$DataDirectories = @(
    (Join-Path $ProjectRoot "docker-data"),
    (Join-Path $ProjectRoot "docker-data\postgres"),
    (Join-Path $ProjectRoot "docker-data\rabbitmq"),
    (Join-Path $ProjectRoot "docker-data\redis"),
    (Join-Path $ProjectRoot "docker-data\minio"),
    (Join-Path $ProjectRoot "docker-data\minio\data")
)
$RequiredPorts = @()
$WindowsServiceTargets = @()
$ProcessTargets = @()

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

function Get-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Load-EnvFile {
    param([string]$Path)

    $map = @{}
    foreach ($rawLine in Get-Content $Path -Encoding utf8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            continue
        }

        $parts = $line -split "=", 2
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        if ($key) {
            $map[$key] = $value
        }
    }

    return $map
}

function Get-ConfiguredPort {
    param(
        [hashtable]$EnvMap,
        [string]$Key,
        [int]$Default
    )

    if ($EnvMap.ContainsKey($Key)) {
        $value = $EnvMap[$Key]
        if ($value -match '^\d+$') {
            return [int]$value
        }
    }

    return $Default
}

function Get-BasicAuthHeaders {
    param(
        [string]$Username,
        [string]$Password
    )

    $pair = "{0}:{1}" -f $Username, $Password
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($pair)
    $token = [Convert]::ToBase64String($bytes)
    return @{ Authorization = "Basic $token" }
}

function Ensure-DataDirectories {
    foreach ($path in $DataDirectories) {
        if (-not (Test-Path $path)) {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
        }
    }
}

function Resolve-DockerDesktopPath {
    $candidates = @(
        "D:\Docker\Docker Desktop.exe",
        "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Test-DockerCli {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw "Docker CLI was not found in PATH."
    }
}

function Test-DockerDaemon {
    try {
        $null = & docker info --format "{{.ServerVersion}}" 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Start-DockerDesktopIfNeeded {
    if (Test-DockerDaemon) {
        return
    }

    $service = Get-Service -Name "com.docker.service" -ErrorAction SilentlyContinue
    if ($null -ne $service -and $service.Status -ne "Running") {
        try {
            Start-Service -Name $service.Name -ErrorAction Stop
        } catch {
            Write-Warning ("Failed to start service {0}: {1}" -f $service.Name, $_.Exception.Message)
        }
    }

    $dockerDesktopPath = Resolve-DockerDesktopPath
    if ($null -eq $dockerDesktopPath) {
        throw "Docker Desktop executable was not found."
    }

    Start-Process -FilePath $dockerDesktopPath | Out-Null
}

function Wait-ForDockerDaemon {
    param([int]$TimeoutSeconds = 120)

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerDaemon) {
            return $true
        }
        Start-Sleep -Seconds 3
    }

    return $false
}

function Invoke-Compose {
    param([string[]]$ComposeArgs)

    & docker compose --env-file $EnvPath -f $ComposePath @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw ("docker compose failed: {0}" -f ($ComposeArgs -join " "))
    }
}

function Invoke-ComposeWithSetupProfile {
    param([string[]]$ComposeArgs)

    & docker compose --profile setup --env-file $EnvPath -f $ComposePath @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw ("docker compose failed: {0}" -f ($ComposeArgs -join " "))
    }
}

function Get-RunningComposeServices {
    if (-not (Test-DockerDaemon)) {
        return @()
    }

    $output = & docker compose --env-file $EnvPath -f $ComposePath ps --status running --services 2>$null
    if ($LASTEXITCODE -ne 0) {
        return @()
    }

    return @($output | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Get-PortListeners {
    param([int]$Port)

    $connections = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    $listeners = @()
    foreach ($connection in $connections) {
        $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
        $listeners += [PSCustomObject]@{
            Port = $Port
            ProcessId = $connection.OwningProcess
            ProcessName = if ($process) { $process.ProcessName } else { "<unknown>" }
        }
    }

    return @($listeners)
}

function Show-PortSummary {
    $rows = @()
    foreach ($port in $RequiredPorts) {
        $listeners = @(Get-PortListeners -Port $port)
        if ($listeners.Count -eq 0) {
            $rows += [PSCustomObject]@{
                Port = $port
                State = "free"
                ProcessName = ""
                ProcessId = ""
            }
            continue
        }

        foreach ($listener in $listeners) {
            $rows += [PSCustomObject]@{
                Port = $listener.Port
                State = "busy"
                ProcessName = $listener.ProcessName
                ProcessId = $listener.ProcessId
            }
        }
    }

    $rows |
        Sort-Object Port, ProcessId |
        Select-Object -Unique Port, State, ProcessName, ProcessId |
        Format-Table -AutoSize
}

function Stop-KnownLocalServices {
    if (-not (Get-IsAdministrator)) {
        throw "Stopping Windows services requires an elevated PowerShell session."
    }

    foreach ($target in $WindowsServiceTargets) {
        $service = Get-Service -Name $target.Name -ErrorAction SilentlyContinue
        if ($null -eq $service) {
            continue
        }

        if ($service.Status -eq "Running") {
            Write-Host ("Stopping Windows service: {0}" -f $target.Label)
            Stop-Service -Name $target.Name -Force -ErrorAction Stop
            $service.WaitForStatus([System.ServiceProcess.ServiceControllerStatus]::Stopped, [TimeSpan]::FromSeconds(30))
        }

        if ($target.Name -eq "RabbitMQ") {
            Write-Host "Disabling Windows service startup: RabbitMQ"
            Set-Service -Name $target.Name -StartupType Disabled -ErrorAction Stop
        }
    }

    foreach ($target in $ProcessTargets) {
        foreach ($port in $target.Ports) {
            $listeners = Get-PortListeners -Port $port
            foreach ($listener in $listeners) {
                if ($target.ProcessNames -contains $listener.ProcessName) {
                    Write-Host ("Stopping local process {0} on port {1} (PID {2})" -f $listener.ProcessName, $port, $listener.ProcessId)
                    Stop-Process -Id $listener.ProcessId -Force -ErrorAction Stop
                }
            }
        }
    }
}

function Assert-NoLocalRabbitMqConflict {
    $service = Get-Service -Name "RabbitMQ" -ErrorAction SilentlyContinue
    if ($null -ne $service -and $service.Status -eq "Running") {
        throw "Local Windows RabbitMQ service is still running. Stop and disable it before using Docker RabbitMQ."
    }

    $listeners = @()
    $listeners += @(Get-PortListeners -Port $RabbitMqPort)
    $listeners += @(Get-PortListeners -Port $RabbitMqManagementPort)
    $erlListeners = @($listeners | Where-Object { $_.ProcessName -eq "erl" })
    if ($erlListeners.Count -gt 0) {
        $detail = ($erlListeners | Sort-Object Port, ProcessId | ForEach-Object {
            "Port {0} is owned by local process {1} (PID {2})" -f $_.Port, $_.ProcessName, $_.ProcessId
        }) -join [Environment]::NewLine
        throw ("Local RabbitMQ/Erlang listeners are still occupying the expected Docker ports.`n{0}" -f $detail)
    }
}

function Assert-PortsAvailable {
    $blocking = @()
    foreach ($port in $RequiredPorts) {
        $blocking += @(Get-PortListeners -Port $port)
    }

    if ($blocking.Count -eq 0) {
        return
    }

    $detail = ($blocking | Sort-Object Port, ProcessId | ForEach-Object {
        "Port {0} is used by {1} (PID {2})" -f $_.Port, $_.ProcessName, $_.ProcessId
    }) -join [Environment]::NewLine

    throw ("Required ports are still occupied.`n{0}`nUse -StopLocalServices for known local services or free those ports manually." -f $detail)
}

function Wait-Until {
    param(
        [scriptblock]$Probe,
        [string]$Description,
        [int]$TimeoutSeconds = 90,
        [int]$IntervalSeconds = 2
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            if (& $Probe) {
                Write-Host ("[ok] {0}" -f $Description)
                return
            }
        } catch {
        }

        Start-Sleep -Seconds $IntervalSeconds
    }

    throw ("Timed out waiting for {0}." -f $Description)
}

function Assert-RabbitMqHostAuthentication {
    param([hashtable]$EnvMap)

    $username = if ($EnvMap.ContainsKey("RABBITMQ_DEFAULT_USER")) { $EnvMap["RABBITMQ_DEFAULT_USER"] } else { "ocr_admin" }
    $password = if ($EnvMap.ContainsKey("RABBITMQ_DEFAULT_PASS")) { $EnvMap["RABBITMQ_DEFAULT_PASS"] } else { "ocr_password123" }
    $managementPort = Get-ConfiguredPort -EnvMap $EnvMap -Key "RABBITMQ_MANAGEMENT_PORT" -Default 15672
    $uri = "http://127.0.0.1:{0}/api/whoami" -f $managementPort
    $headers = Get-BasicAuthHeaders -Username $username -Password $password

    try {
        $response = Invoke-WebRequest -Uri $uri -Headers $headers -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        $payload = $response.Content | ConvertFrom-Json
    } catch {
        $message = if ($_.Exception.Response) {
            "RabbitMQ management API rejected the configured Docker credentials. This usually means local RabbitMQ is still bound to the expected management port."
        } else {
            ("RabbitMQ management API is not reachable on 127.0.0.1:{0}." -f $managementPort)
        }
        throw $message
    }

    if ($payload.name -ne $username) {
        throw ("RabbitMQ management API responded as '{0}' instead of expected Docker user '{1}'." -f $payload.name, $username)
    }

    Write-Host ("[ok] RabbitMQ host authentication via {0}" -f $uri)
}

function Test-TcpPort {
    param([int]$Port)

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $connected = $iar.AsyncWaitHandle.WaitOne(2000, $false)
        if (-not $connected) {
            return $false
        }
        $client.EndConnect($iar)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Invoke-MiddlewareHealthChecks {
    $envMap = Load-EnvFile -Path $EnvPath
    $postgresUser = if ($envMap.ContainsKey("POSTGRES_USER")) { $envMap["POSTGRES_USER"] } else { "postgres" }
    $postgresDb = if ($envMap.ContainsKey("POSTGRES_DB")) { $envMap["POSTGRES_DB"] } else { "ocr_db" }
    $bucketName = if ($envMap.ContainsKey("OCR_STORAGE_BUCKET")) { $envMap["OCR_STORAGE_BUCKET"] } else { "ocr-source" }
    $minioConsolePort = Get-ConfiguredPort -EnvMap $envMap -Key "MINIO_CONSOLE_PORT" -Default 9001
    $minioEndpoint = if ($envMap.ContainsKey("OCR_STORAGE_ENDPOINT")) { $envMap["OCR_STORAGE_ENDPOINT"] } else { "http://127.0.0.1:9000" }

    Write-Section "Health checks"

    Wait-Until -Description "PostgreSQL readiness" -Probe {
        & docker compose --env-file $EnvPath -f $ComposePath exec -T postgres pg_isready -U $postgresUser -d $postgresDb *> $null
        $LASTEXITCODE -eq 0
    }

    Wait-Until -Description ("Database {0} exists" -f $postgresDb) -Probe {
        $result = & docker compose --env-file $EnvPath -f $ComposePath exec -T postgres `
            psql -U $postgresUser -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '$postgresDb';" 2>$null
        ($LASTEXITCODE -eq 0) -and (($result | Out-String).Trim() -eq "1")
    }

    Wait-Until -Description "RabbitMQ readiness" -Probe {
        & docker compose --env-file $EnvPath -f $ComposePath exec -T rabbitmq rabbitmq-diagnostics -q ping *> $null
        $LASTEXITCODE -eq 0
    }

    Assert-RabbitMqHostAuthentication -EnvMap $envMap

    Wait-Until -Description "Redis readiness" -Probe {
        $result = & docker compose --env-file $EnvPath -f $ComposePath exec -T redis redis-cli ping 2>$null
        ($LASTEXITCODE -eq 0) -and (($result | Out-String).Trim() -eq "PONG")
    }

    Wait-Until -Description "MinIO API readiness" -Probe {
        try {
            $response = Invoke-WebRequest -Uri ("{0}/minio/health/live" -f $minioEndpoint.TrimEnd("/")) -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            $response.StatusCode -eq 200
        } catch {
            $false
        }
    }

    Wait-Until -Description "MinIO Console readiness" -Probe {
        Test-TcpPort -Port $minioConsolePort
    }

    Write-Section "Ensuring MinIO bucket"
    Invoke-ComposeWithSetupProfile -ComposeArgs @("run", "--rm", "minio-init")
    Write-Host ("[ok] Bucket ensured: {0}" -f $bucketName)
}

function Show-UsageHints {
    $envMap = Load-EnvFile -Path $EnvPath
    $postgresPort = Get-ConfiguredPort -EnvMap $envMap -Key "POSTGRES_PORT" -Default 5432
    $rabbitMqPort = Get-ConfiguredPort -EnvMap $envMap -Key "RABBITMQ_PORT" -Default 5672
    $rabbitMqManagementPort = Get-ConfiguredPort -EnvMap $envMap -Key "RABBITMQ_MANAGEMENT_PORT" -Default 15672
    $redisPort = Get-ConfiguredPort -EnvMap $envMap -Key "REDIS_PORT" -Default 6379
    $minioConsolePort = Get-ConfiguredPort -EnvMap $envMap -Key "MINIO_CONSOLE_PORT" -Default 9001

    Write-Section "Access"
    Write-Host ("PostgreSQL : 127.0.0.1:{0}" -f $postgresPort)
    Write-Host ("RabbitMQ   : amqp://127.0.0.1:{0}" -f $rabbitMqPort)
    Write-Host ("RabbitMQ UI: http://127.0.0.1:{0}" -f $rabbitMqManagementPort)
    Write-Host ("Redis      : 127.0.0.1:{0}" -f $redisPort)
    Write-Host ("MinIO API  : {0}" -f $envMap["OCR_STORAGE_ENDPOINT"])
    Write-Host ("MinIO UI   : http://127.0.0.1:{0}" -f $minioConsolePort)
    Write-Host ""
    Write-Host "Default credentials"
    Write-Host ("- PostgreSQL : {0} / {1}" -f $envMap["POSTGRES_USER"], $envMap["POSTGRES_PASSWORD"])
    Write-Host ("- RabbitMQ   : {0} / {1}" -f $envMap["RABBITMQ_DEFAULT_USER"], $envMap["RABBITMQ_DEFAULT_PASS"])
    Write-Host ("- MinIO      : {0} / {1}" -f $envMap["OCR_STORAGE_ACCESS_KEY"], $envMap["OCR_STORAGE_SECRET_KEY"])
    Write-Host ""
    Write-Host "App-facing environment variables"
    Write-Host ("- DATABASE_URL={0}" -f $envMap["DATABASE_URL"])
    Write-Host ("- REDIS_URL={0}" -f $envMap["REDIS_URL"])
    Write-Host ("- MQ_BROKER_URL={0}" -f $envMap["MQ_BROKER_URL"])
    Write-Host ("- OCR_STORAGE_ENDPOINT={0}" -f $envMap["OCR_STORAGE_ENDPOINT"])
}

function Show-Status {
    Write-Section "Project files"
    Write-Host ("Compose file : {0}" -f $ComposePath)
    Write-Host ("Env file     : {0}" -f $EnvPath)

    Write-Section "Windows services"
    Get-Service -Name "postgresql-x64-17", "RabbitMQ", "com.docker.service" -ErrorAction SilentlyContinue |
        Select-Object Status, Name, DisplayName |
        Format-Table -AutoSize

    Write-Section "Port summary"
    Show-PortSummary

    Write-Section "Docker daemon"
    if (Test-DockerDaemon) {
        & docker info --format "ServerVersion={{.ServerVersion}}  Context={{.ClientInfo.Context}}"
        Write-Section "Compose services"
        Invoke-Compose -ComposeArgs @("ps")
    } else {
        Write-Host "Docker daemon is not running."
    }
}

Assert-PathExists -Path $ComposePath -Label "Compose file"
Assert-PathExists -Path $EnvPath -Label "Docker env file"

$ConfiguredEnv = Load-EnvFile -Path $EnvPath
$PostgresPort = Get-ConfiguredPort -EnvMap $ConfiguredEnv -Key "POSTGRES_PORT" -Default 5432
$RabbitMqPort = Get-ConfiguredPort -EnvMap $ConfiguredEnv -Key "RABBITMQ_PORT" -Default 5672
$RabbitMqManagementPort = Get-ConfiguredPort -EnvMap $ConfiguredEnv -Key "RABBITMQ_MANAGEMENT_PORT" -Default 15672
$RedisPort = Get-ConfiguredPort -EnvMap $ConfiguredEnv -Key "REDIS_PORT" -Default 6379
$MinioPort = Get-ConfiguredPort -EnvMap $ConfiguredEnv -Key "MINIO_PORT" -Default 9000
$MinioConsolePort = Get-ConfiguredPort -EnvMap $ConfiguredEnv -Key "MINIO_CONSOLE_PORT" -Default 9001
$RequiredPorts = @($PostgresPort, $RabbitMqPort, $RedisPort, $MinioPort, $MinioConsolePort, $RabbitMqManagementPort)
$WindowsServiceTargets = @(
    @{
        Name = "postgresql-x64-17"
        Label = "PostgreSQL"
        Ports = @($PostgresPort)
    },
    @{
        Name = "RabbitMQ"
        Label = "RabbitMQ"
        Ports = @($RabbitMqPort, $RabbitMqManagementPort)
    }
)
$ProcessTargets = @(
    @{
        ProcessNames = @("redis-server")
        Label = "Redis"
        Ports = @($RedisPort)
    },
    @{
        ProcessNames = @("minio")
        Label = "MinIO"
        Ports = @($MinioPort, $MinioConsolePort)
    }
)

switch ($Action) {
    "Validate" {
        Test-DockerCli
        Ensure-DataDirectories
        Write-Section "Validating docker compose configuration"
        & docker compose --env-file $EnvPath -f $ComposePath config | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose config failed."
        }
        Write-Host "Compose configuration is valid."
        Show-UsageHints
    }
    "Status" {
        Test-DockerCli
        Show-Status
    }
    "Up" {
        Test-DockerCli
        Ensure-DataDirectories

        $runningServices = @(Get-RunningComposeServices)
        if ($runningServices.Count -gt 0) {
            if ($StopLocalServices) {
                Write-Section "Stopping known local middleware services"
                Stop-KnownLocalServices
            }
            Assert-NoLocalRabbitMqConflict
            Write-Section "Middleware containers currently running"
            Write-Host ($runningServices -join ", ")
            Write-Host "Ensuring all middleware services are up."
            Invoke-Compose -ComposeArgs @("up", "-d", "postgres", "rabbitmq", "redis", "minio")
            Invoke-MiddlewareHealthChecks
            Show-Status
            Show-UsageHints
            return
        }

        if ($StopLocalServices) {
            Write-Section "Stopping known local middleware services"
            Stop-KnownLocalServices
        }

        Assert-NoLocalRabbitMqConflict

        Write-Section "Checking required ports"
        Assert-PortsAvailable
        Write-Host "All required ports are free."

        Write-Section "Starting Docker Desktop"
        Start-DockerDesktopIfNeeded
        if (-not (Wait-ForDockerDaemon -TimeoutSeconds $DockerStartupTimeoutSeconds)) {
            throw "Docker daemon did not become ready in time."
        }
        Write-Host "Docker daemon is ready."

        Write-Section "Validating compose configuration"
        & docker compose --env-file $EnvPath -f $ComposePath config | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "docker compose config failed."
        }

        Write-Section "Starting middleware containers"
        Invoke-Compose -ComposeArgs @("up", "-d", "postgres", "rabbitmq", "redis", "minio")

        Invoke-MiddlewareHealthChecks
        Show-Status
        Show-UsageHints
    }
    "Down" {
        Test-DockerCli
        if (-not (Test-DockerDaemon)) {
            Write-Host "Docker daemon is not running. Nothing to stop."
            return
        }

        Write-Section "Stopping middleware containers"
        $args = @("down", "--remove-orphans")
        if ($DestroyData) {
            $args += "-v"
        }
        Invoke-Compose -ComposeArgs $args
        Show-Status
    }
    "Restart" {
        Test-DockerCli
        if (Test-DockerDaemon) {
            Write-Section "Restarting middleware containers"
            Invoke-Compose -ComposeArgs @("down", "--remove-orphans")
        }

        Ensure-DataDirectories
        if ($StopLocalServices) {
            Write-Section "Stopping known local middleware services"
            Stop-KnownLocalServices
        }

        Assert-NoLocalRabbitMqConflict

        Write-Section "Checking required ports"
        Assert-PortsAvailable
        Write-Host "All required ports are free."

        Write-Section "Starting Docker Desktop"
        Start-DockerDesktopIfNeeded
        if (-not (Wait-ForDockerDaemon -TimeoutSeconds $DockerStartupTimeoutSeconds)) {
            throw "Docker daemon did not become ready in time."
        }
        Write-Host "Docker daemon is ready."

        Write-Section "Starting middleware containers"
        Invoke-Compose -ComposeArgs @("up", "-d", "postgres", "rabbitmq", "redis", "minio")

        Invoke-MiddlewareHealthChecks
        Show-Status
        Show-UsageHints
    }
}
