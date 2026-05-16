param(
    [string[]]$Models = @("granite4.1:30b", "gemma4:31b", "qwen3.6:35b"),
    [string]$Distro = "Ubuntu-24.04"
)

$ErrorActionPreference = "Continue"

Write-Host "Stopping REI probe Python processes..." -ForegroundColor Yellow
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

Write-Host "Unloading Ollama models..." -ForegroundColor Yellow
foreach ($model in $Models) {
    try {
        wsl.exe -d $Distro -- ollama stop $model | Out-Null
        Write-Host "Requested ollama stop $model" -ForegroundColor Green
    } catch {
        Write-Host "Could not stop ${model}: $_" -ForegroundColor DarkYellow
    }
}

Write-Host "Current Ollama state:" -ForegroundColor Yellow
wsl.exe -d $Distro -- ollama ps

Write-Host "Resetting terminal colors/cursor." -ForegroundColor Yellow
Write-Host "$([char]27)[0m$([char]27)[?25h"
