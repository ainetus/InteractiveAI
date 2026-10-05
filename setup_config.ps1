# setup_config.ps1
# Loads the Railway business config into OperatorFabric.
# Uses only Windows built-in tools (tar, curl, PowerShell).
# Run automatically by start.bat

param(
    [string]$BaseUrl = "http://localhost:3200"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundleDir = Join-Path $ScriptDir "resources\bundles\cab-bundle"
$TarFile   = Join-Path $env:TEMP "cab-bundle.tar.gz"

Write-Host "      Getting auth token..."
$tokenResponse = curl.exe -s -X POST "$BaseUrl/auth/token" `
    -d "username=admin&password=test&grant_type=password&client_id=opfab-client" `
    | ConvertFrom-Json

$token = $tokenResponse.access_token
if (-not $token) {
    Write-Host "      ERROR: Could not get auth token. Services may not be ready yet."
    exit 1
}

Write-Host "      Uploading business config bundle..."
Push-Location $BundleDir
tar.exe -czf $TarFile . 2>$null
Pop-Location

$result = curl.exe -s -o NUL -w "%{http_code}" -X POST "$BaseUrl/businessconfig/processes" `
    -H "Authorization: Bearer $token" `
    -F "file=@$TarFile;type=application/gzip"

if ($result -eq "201") {
    Write-Host "      Bundle uploaded successfully."
} else {
    Write-Host "      Bundle upload returned: $result (may already exist)"
}

Write-Host "      Assigning perimeters to groups..."

# Create perimeter
$perimeterJson = '{"id":"cabProcess","process":"cabProcess","stateRights":[{"state":"messageState","rights":"ReceiveAndWrite"}]}'
curl.exe -s -o NUL -X POST "$BaseUrl/users/perimeters" `
    -H "Authorization: Bearer $token" `
    -H "Content-Type: application/json" `
    -d $perimeterJson

# Assign to groups
curl.exe -s -o NUL -X PUT "$BaseUrl/users/groups/Dispatcher/perimeters" `
    -H "Authorization: Bearer $token" `
    -H "Content-Type: application/json" `
    -d '["cabProcess"]'

curl.exe -s -o NUL -X PUT "$BaseUrl/users/groups/Planner/perimeters" `
    -H "Authorization: Bearer $token" `
    -H "Content-Type: application/json" `
    -d '["cabProcess"]'

Write-Host "      Perimeters assigned. Notification cards should work."
