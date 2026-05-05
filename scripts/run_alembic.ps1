$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $repo ".env"
$envMap = @{}

Get-Content $envPath | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
        $k, $v = $line.Split("=", 2)
        $envMap[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
    }
}

$user = $envMap["POSTGRES_USER"]
$password = [uri]::EscapeDataString($envMap["POSTGRES_PASSWORD"])
$db = $envMap["POSTGRES_DB"]
$hostName = if ($envMap["POSTGRES_HOST"]) { $envMap["POSTGRES_HOST"] } else { "localhost" }
$port = if ($envMap["POSTGRES_HOST_PORT"]) { $envMap["POSTGRES_HOST_PORT"] } else { "55432" }

$env:DATABASE_URL = "postgresql+psycopg://${user}:${password}@${hostName}:${port}/${db}"
python -m alembic -c (Join-Path $repo "alembic.ini") @args
