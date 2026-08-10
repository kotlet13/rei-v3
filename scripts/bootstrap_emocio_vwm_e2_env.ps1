param(
    [Parameter(Mandatory = $true)]
    [string]$PythonExe,
    [Parameter(Mandatory = $true)]
    [string]$ReportDirectory
)

$ErrorActionPreference = "Stop"
$reportRoot = [System.IO.Path]::GetFullPath($ReportDirectory)
[System.IO.Directory]::CreateDirectory($reportRoot) | Out-Null

& $PythonExe -m pip install `
    --index-url https://download.pytorch.org/whl/cu130 `
    "torch==2.11.0" "torchvision==0.26.0" `
    --report ([System.IO.Path]::Combine($reportRoot, "torch-install-report.json"))
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $PythonExe -m pip install `
    "accelerate==1.5.2" `
    "einops==0.8.0" `
    "h5py==3.12.1" `
    "imageio==2.37.0" `
    "matplotlib==3.10.1" `
    "numpy==1.26.4" `
    "opencv-python==4.11.0.86" `
    "piqa==1.3.2" `
    "pillow==11.1.0" `
    "requests==2.32.3" `
    "scikit-image==0.25.2" `
    "tqdm==4.67.1" `
    "ttkthemes==3.2.2" `
    "ttkwidgets==0.13.0" `
    --report ([System.IO.Path]::Combine($reportRoot, "dependencies-install-report.json"))
exit $LASTEXITCODE
