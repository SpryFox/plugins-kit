param([string]$DirSuffix = ".local/bin")

$target = Join-Path $env:USERPROFILE $DirSuffix
$current = [Environment]::GetEnvironmentVariable("Path", "User")

# Check if already present (case-insensitive)
$entries = $current -split ";" | ForEach-Object { $_.TrimEnd("\", "/") }
$normalizedTarget = $target.TrimEnd("\", "/")

if ($entries -icontains $normalizedTarget) {
    Write-Host "Already in PATH: $target"
    exit 0
}

[Environment]::SetEnvironmentVariable("Path", $current + ";" + $target, "User")
Write-Host "Added to PATH: $target"
