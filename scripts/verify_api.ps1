param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$baseUrl = "http://127.0.0.1:$Port"
$env:PYTHONPATH = Join-Path $projectRoot "src"
$env:HOSPITAL_PROJECT_ROOT = $projectRoot

if (-not (Test-Path -LiteralPath $python)) {
    throw "Environnement Python introuvable : $python"
}

function Get-HttpStatus {
    param([scriptblock]$Request)
    try {
        & $Request | Out-Null
        return 200
    }
    catch {
        if ($_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode
        }
        throw
    }
}

$server = Start-Process `
    -FilePath $python `
    -ArgumentList "-m uvicorn hospital_planning.api.app:app --host 127.0.0.1 --port $Port --log-level warning" `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -PassThru

try {
    $health = $null
    foreach ($attempt in 1..30) {
        try {
            $health = Invoke-RestMethod "$baseUrl/health" -TimeoutSec 2
            break
        }
        catch {
            Start-Sleep -Milliseconds 300
        }
    }
    if ($null -eq $health) {
        throw "Le serveur FastAPI ne répond pas après 9 secondes."
    }

    $config = Invoke-RestMethod "$baseUrl/api/v1/config/hospital"
    $job = Invoke-RestMethod `
        "$baseUrl/api/v1/jobs/experiments" `
        -Method Post `
        -ContentType "application/json" `
        -Body '{"scenario_ids":["S0_BASELINE"],"methods":["greedy"],"seed":42}'

    $observedStates = @($job.status)
    $finalJob = $job
    foreach ($attempt in 1..100) {
        $finalJob = Invoke-RestMethod "$baseUrl/api/v1/jobs/$($job.job_id)"
        if ($observedStates[-1] -ne $finalJob.status) {
            $observedStates += $finalJob.status
        }
        if ($finalJob.status -in @("COMPLETED", "FAILED")) {
            break
        }
        Start-Sleep -Milliseconds 200
    }
    if ($finalJob.status -ne "COMPLETED") {
        throw "Le job est dans l'état $($finalJob.status) : $($finalJob.error_message)"
    }

    $experimentId = $finalJob.experiment_ids[0]
    $experiment = Invoke-RestMethod "$baseUrl/api/v1/experiments/$experimentId"
    $downloadPath = Join-Path $env:TEMP "hospital-planning-$experimentId-bed_allocations.csv"
    $download = Invoke-WebRequest `
        "$baseUrl/api/v1/experiments/$experimentId/downloads/greedy/bed_allocations.csv" `
        -OutFile $downloadPath
    $unknownJobStatus = Get-HttpStatus { Invoke-WebRequest "$baseUrl/api/v1/jobs/no-such-job" -ErrorAction Stop }
    $invalidRequestStatus = Get-HttpStatus {
        Invoke-WebRequest "$baseUrl/api/v1/jobs/experiments" -Method Post -ContentType "application/json" -Body '{"methods":[]}' -ErrorAction Stop
    }
    $traversalStatus = Get-HttpStatus {
        Invoke-WebRequest "$baseUrl/api/v1/experiments/$experimentId/downloads/%2E%2E%2Fexperiment.json" -ErrorAction Stop
    }
    $cors = Invoke-WebRequest `
        "$baseUrl/api/v1/jobs/experiments" `
        -Method Options `
        -Headers @{Origin = "http://localhost:3011"; "Access-Control-Request-Method" = "POST"}

    [pscustomobject]@{
        health_status = $health.status
        planning_horizon_days = $config.planning_horizon_days
        submitted_job_status = $job.status
        observed_job_states = $observedStates -join ","
        final_job_status = $finalJob.status
        experiment_id = $experimentId
        kpi_method_status = $experiment.metrics[0].status
        download_http_status = $download.StatusCode
        download_bytes = (Get-Item -LiteralPath $downloadPath).Length
        unknown_job_http_status = $unknownJobStatus
        invalid_request_http_status = $invalidRequestStatus
        traversal_http_status = $traversalStatus
        cors_origin = $cors.Headers["access-control-allow-origin"]
        cors_methods = $cors.Headers["access-control-allow-methods"]
        persistence_note = "Les expériences restent sur disque; les jobs en mémoire disparaissent au redémarrage."
    } | ConvertTo-Json -Depth 4
}
finally {
    if (-not $server.HasExited) {
        Stop-Process -Id $server.Id -Force
    }
}
