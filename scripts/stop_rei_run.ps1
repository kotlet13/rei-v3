param(
    [string[]]$Models = @(),
    [string]$Distro = "Ubuntu-24.04"
)

$ErrorActionPreference = "Continue"

Write-Host "Stopping REI Python processes..." -ForegroundColor Yellow
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match "run_rei_" -and $_.Name -match "python|python3" } |
    ForEach-Object {
        try {
            Stop-Process -Id $_.ProcessId -Force
            Write-Host "Stopped $($_.ProcessId) $($_.Name)" -ForegroundColor Green
        } catch {
            Write-Host "Already stopped $($_.ProcessId)" -ForegroundColor DarkGray
        }
    }

$requestedModels = @(
    $Models |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
)
if ($requestedModels.Count -eq 0) {
    Write-Host "No Ollama models requested for unloading; pass -Models explicitly to opt in." -ForegroundColor DarkGray
} else {
    Write-Host "Unloading explicitly requested Ollama models..." -ForegroundColor Yellow
    foreach ($model in $requestedModels) {
        try {
            wsl.exe -d $Distro -- ollama stop $model | Out-Null
            Write-Host "Requested ollama stop $model" -ForegroundColor Green
        } catch {
            Write-Host "Could not stop ${model}: $_" -ForegroundColor DarkYellow
        }
    }
}

Write-Host "Current Ollama state:" -ForegroundColor Yellow
wsl.exe -d $Distro -- ollama ps

Write-Host "Resetting terminal colors/cursor." -ForegroundColor Yellow
Write-Host "$([char]27)[0m$([char]27)[?25h"
