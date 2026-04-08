[CmdletBinding()]
param(
    [string]$BaseUrl = "http://localhost:8000",
    [int]$TaskId = 0,
    [string]$BatchId = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ResponseBodyFromException {
    param([System.Exception]$Exception)

    try {
        if ($null -eq $Exception.Response) {
            return ""
        }
        $stream = $Exception.Response.GetResponseStream()
        if ($null -eq $stream) {
            return ""
        }
        $reader = New-Object System.IO.StreamReader($stream)
        try {
            return $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
    } catch {
        return ""
    }
}

function Get-ErrorKind {
    param(
        [int]$StatusCode,
        [string]$Message
    )

    if ($StatusCode -in @(502, 503, 504)) { return "upstream_model_error" }
    if ($StatusCode -in @(400, 404, 409)) { return "business_error" }
    if ($StatusCode -ge 500) { return "server_error" }
    if ($Message -match "The operation has timed out|operation has timed out|Request timed out|Read timed out|Connect timeout|timeout") {
        return "request_timeout"
    }

    if ($Message -match "ECONNREFUSED|ERR_CONNECTION_REFUSED|connection refused|No connection could be made|actively refused|Unable to connect|无法连接到远程服务器") {
        return "backend_unready"
    }
    if ($Message -match "ERR_NETWORK_CHANGED|network changed|Failed to fetch|Network request failed") {
        return "network_transient"
    }
    return "unknown_error"
}

function Try-ParseJson {
    param([string]$Content)

    if ([string]::IsNullOrWhiteSpace($Content)) {
        return $null
    }

    try {
        return $Content | ConvertFrom-Json -Depth 100
    } catch {
        return $null
    }
}

function Invoke-ApiCheck {
    param(
        [string]$Name,
        [ValidateSet("GET", "POST")]
        [string]$Method,
        [string]$Path,
        [object]$Body = $null,
        [int]$TimeoutSec = 20
    )

    $uri = "{0}{1}" -f $BaseUrl.TrimEnd("/"), $Path
    $params = @{
        Method      = $Method
        Uri         = $uri
        TimeoutSec  = $TimeoutSec
        UseBasicParsing = $true
        ErrorAction = "Stop"
    }

    if ($Method -eq "POST") {
        $params.ContentType = "application/json"
        $params.Body = if ($null -eq $Body) { "{}" } else { ($Body | ConvertTo-Json -Depth 20 -Compress) }
    }

    try {
        $resp = Invoke-WebRequest @params
        return [PSCustomObject]@{
            name    = $Name
            method  = $Method
            path    = $Path
            status  = [int]$resp.StatusCode
            ok      = $true
            kind    = "ok"
            detail  = ""
            content = [string]$resp.Content
        }
    } catch {
        $status = 0
        if ($_.Exception.Response -and $_.Exception.Response.StatusCode) {
            $status = [int]$_.Exception.Response.StatusCode
        }
        $body = Get-ResponseBodyFromException -Exception $_.Exception
        $detail = ("{0} {1}" -f $_.Exception.Message, $body).Trim()
        $kind = Get-ErrorKind -StatusCode $status -Message $detail
        return [PSCustomObject]@{
            name    = $Name
            method  = $Method
            path    = $Path
            status  = $status
            ok      = $false
            kind    = $kind
            detail  = $detail
            content = $body
        }
    }
}

function Resolve-TaskId {
    param([int]$InputTaskId)
    if ($InputTaskId -gt 0) {
        return $InputTaskId
    }

    $result = Invoke-ApiCheck -Name "tasks-list-for-taskid" -Method "GET" -Path "/api/ocr/tasks?page=1&page_size=100"
    if (-not $result.ok) {
        return 0
    }

    $json = Try-ParseJson -Content $result.content
    if ($null -eq $json -or $null -eq $json.tasks) {
        return 0
    }

    $done = $json.tasks | Where-Object { $_.status -eq "done" } | Select-Object -First 1
    if ($null -ne $done -and $done.id) {
        return [int]$done.id
    }
    return 0
}

function Resolve-BatchId {
    param([string]$InputBatchId)
    if (-not [string]::IsNullOrWhiteSpace($InputBatchId)) {
        return $InputBatchId.Trim()
    }

    $result = Invoke-ApiCheck -Name "archive-records-for-batchid" -Method "GET" -Path "/api/ocr/archive-records?page=1&page_size=300"
    if (-not $result.ok) {
        return ""
    }

    $json = Try-ParseJson -Content $result.content
    if ($null -eq $json -or $null -eq $json.records) {
        return ""
    }

    $batch = $json.records |
        Where-Object { $_.batch_id -match "^batch_" } |
        Select-Object -First 1

    if ($null -ne $batch -and -not [string]::IsNullOrWhiteSpace($batch.batch_id)) {
        return [string]$batch.batch_id
    }
    return ""
}

$checks = New-Object System.Collections.Generic.List[object]

$checks.Add((Invoke-ApiCheck -Name "health" -Method "GET" -Path "/api/health"))
$checks.Add((Invoke-ApiCheck -Name "folders" -Method "GET" -Path "/api/ocr/tasks/folders"))

$resolvedTaskId = Resolve-TaskId -InputTaskId $TaskId
$resolvedBatchId = Resolve-BatchId -InputBatchId $BatchId

if ($resolvedTaskId -gt 0) {
    $checks.Add((Invoke-ApiCheck -Name "ai-extract-fields" -Method "POST" -Path "/api/ocr/tasks/$resolvedTaskId/ai-extract-fields" -Body @{
        persist = $false
        include_evidence = $true
    } -TimeoutSec 180))
} else {
    $checks.Add([PSCustomObject]@{
        name = "ai-extract-fields"
        method = "POST"
        path = "/api/ocr/tasks/{id}/ai-extract-fields"
        status = 0
        ok = $false
        kind = "skipped"
        detail = "No done task id found. Pass -TaskId to force check."
        content = ""
    })
}

if (-not [string]::IsNullOrWhiteSpace($resolvedBatchId)) {
    $encodedBatch = [uri]::EscapeDataString($resolvedBatchId)
    $checks.Add((Invoke-ApiCheck -Name "ai-merge-extract" -Method "POST" -Path "/api/ocr/batches/$encodedBatch/ai-merge-extract" -Body @{
        include_evidence = $true
        persist = $false
        force_refresh = $false
    } -TimeoutSec 300))
    $checks.Add((Invoke-ApiCheck -Name "evaluation-metrics" -Method "GET" -Path "/api/ocr/batches/$encodedBatch/evaluation-metrics?force_refresh=false" -TimeoutSec 120))
    $checks.Add((Invoke-ApiCheck -Name "batch-qa" -Method "POST" -Path "/api/ocr/batches/$encodedBatch/qa" -Body @{
        question = "Summarize the key content of this batch."
        top_k = 6
        persist = $false
    } -TimeoutSec 180))
} else {
    $checks.Add([PSCustomObject]@{
        name = "ai-merge-extract"
        method = "POST"
        path = "/api/ocr/batches/{batch_id}/ai-merge-extract"
        status = 0
        ok = $false
        kind = "skipped"
        detail = "No actionable batch id found. Pass -BatchId to force check."
        content = ""
    })
    $checks.Add([PSCustomObject]@{
        name = "evaluation-metrics"
        method = "GET"
        path = "/api/ocr/batches/{batch_id}/evaluation-metrics"
        status = 0
        ok = $false
        kind = "skipped"
        detail = "No actionable batch id found. Pass -BatchId to force check."
        content = ""
    })
    $checks.Add([PSCustomObject]@{
        name = "batch-qa"
        method = "POST"
        path = "/api/ocr/batches/{batch_id}/qa"
        status = 0
        ok = $false
        kind = "skipped"
        detail = "No actionable batch id found. Pass -BatchId to force check."
        content = ""
    })
}

Write-Host ""
Write-Host "Local self-check target: $BaseUrl"
Write-Host "Resolved task id: $resolvedTaskId"
Write-Host "Resolved batch id: $resolvedBatchId"
Write-Host ""

$checks |
    Select-Object name, method, path, status, ok, kind |
    Format-Table -AutoSize

$blockingKinds = @("backend_unready", "server_error", "upstream_model_error", "request_timeout", "unknown_error")
$blocking = @($checks | Where-Object { -not $_.ok -and ($blockingKinds -contains $_.kind) })

if ($blocking.Count -gt 0) {
    Write-Host ""
    Write-Host "Blocking issues detected:"
    foreach ($item in $blocking) {
        Write-Host ("- {0}: [{1}] {2}" -f $item.name, $item.kind, $item.detail)
    }
    exit 1
}

Write-Host ""
Write-Host "Self-check completed. No blocking issues found."
exit 0
