param(
    [Parameter(Mandatory = $true)]
    [string]$CacheDirectory,
    [Parameter(Mandatory = $true)]
    [string]$ManifestPath
)

$ErrorActionPreference = "Stop"
$cacheRoot = [System.IO.Path]::GetFullPath($CacheDirectory)
[System.IO.Directory]::CreateDirectory($cacheRoot) | Out-Null

$sources = @(
    @{
        Name = "alexnet-owt-7be5be79.pth"
        Url = "https://download.pytorch.org/models/alexnet-owt-7be5be79.pth"
    },
    @{
        Name = "alex.pth"
        Url = "https://github.com/richzhang/PerceptualSimilarity/raw/master/lpips/weights/v0.1/alex.pth"
    }
)

$records = @()
foreach ($source in $sources) {
    $target = [System.IO.Path]::Combine($cacheRoot, $source.Name)
    if (-not [System.IO.File]::Exists($target)) {
        Invoke-WebRequest -Uri $source.Url -OutFile $target -UseBasicParsing
    }
    $file = Get-Item -LiteralPath $target
    $hash = Get-FileHash -LiteralPath $target -Algorithm SHA256
    $records += [ordered]@{
        name = $source.Name
        bytes = $file.Length
        sha256 = $hash.Hash.ToLowerInvariant()
        source = $source.Url
    }
}

$manifest = [ordered]@{
    schema_version = "rei-emocio-vwm-e2-metric-weights-v1"
    acquisition = "explicit_after_protocol_push"
    files = $records
}
$json = $manifest | ConvertTo-Json -Depth 6
[System.IO.File]::WriteAllText([System.IO.Path]::GetFullPath($ManifestPath), $json + "`n", [System.Text.UTF8Encoding]::new($false))
