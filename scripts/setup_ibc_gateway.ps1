param(
    [string]$IbcVersion = "3.23.0",
    [string]$InstallRoot = "C:\IBC",
    [string]$ConfigRoot = "$env:USERPROFILE\Documents\IBC\AlphaEdge",
    [string]$EnvFilePath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Content,
        [switch]$Ascii
    )

    $directory = Split-Path -Parent $Path
    if ($directory) {
        New-Item -ItemType Directory -Path $directory -Force | Out-Null
    }

    if ($Ascii) {
        $encoding = [System.Text.ASCIIEncoding]::new()
    }
    else {
        $encoding = [System.Text.UTF8Encoding]::new($false)
    }

    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Read-EnvMap {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        throw "Env file not found: $Path"
    }

    $values = @{}
    foreach ($line in Get-Content $Path) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        if ($line.TrimStart().StartsWith("#")) {
            continue
        }
        $parts = $line.Split("=", 2)
        if ($parts.Count -ne 2) {
            continue
        }
        $values[$parts[0].Trim()] = $parts[1]
    }
    return $values
}

function Set-OrAppend-EnvValue {
    param(
        [AllowEmptyString()]
        [Parameter(Mandatory = $true)]
        [string[]]$Lines,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $updated = $false
    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -match "^$([regex]::Escape($Key))=") {
            $Lines[$i] = "$Key=$Value"
            $updated = $true
            break
        }
    }

    if (-not $updated) {
        $list = [System.Collections.Generic.List[string]]::new()
        foreach ($line in $Lines) {
            $list.Add($line)
        }
        $list.Add("$Key=$Value")
        return $list.ToArray()
    }

    return $Lines
}

function Set-IniValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Content,
        [Parameter(Mandatory = $true)]
        [string]$Key,
        [Parameter(Mandatory = $true)]
        [string]$Value
    )

    $escapedKey = [regex]::Escape($Key)
    $pattern = "(?m)^$escapedKey=.*$"
    $replacement = "${Key}=${Value}"
    if ([regex]::IsMatch($Content, $pattern)) {
        return [regex]::Replace($Content, $pattern, $replacement, 1)
    }

    return ($Content.TrimEnd("`r", "`n") + "`r`n" + $replacement + "`r`n")
}

function Get-GatewayDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$EnvMap
    )

    $rawPath = $EnvMap["ALPHAEDGE_IB_GATEWAY_PATH"]
    if ($rawPath) {
        $candidate = [System.IO.Path]::GetFullPath($rawPath)
        if (Test-Path $candidate) {
            $item = Get-Item $candidate
            if ($item.PSIsContainer) {
                return $item.FullName
            }
            return $item.Directory.FullName
        }
    }

    $base = "C:\Jts\ibgateway"
    if (-not (Test-Path $base)) {
        throw "IB Gateway installation not found under C:\Jts\ibgateway"
    }

    $latest = Get-ChildItem -Path $base -Directory |
        Sort-Object Name -Descending |
        Select-Object -First 1

    if ($null -eq $latest) {
        throw "No IB Gateway version directory found under $base"
    }

    return $latest.FullName
}

function Get-GatewayMajorVersion {
    param(
        [Parameter(Mandatory = $true)]
        [string]$GatewayDirectory
    )

    $name = Split-Path -Leaf $GatewayDirectory
    if ($name -match "^\d+$") {
        return $name
    }

    $match = [regex]::Match($GatewayDirectory, "\\ibgateway\\(\d+)(\\|$)")
    if ($match.Success) {
        return $match.Groups[1].Value
    }

    throw "Cannot infer IB Gateway major version from path: $GatewayDirectory"
}

function Write-BootstrapJtsIni {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$ApiPort
    )

    if (Test-Path $Path) {
        return
    }

    $content = @(
        "[Logon]",
        "s3store=true",
        "Locale=en",
        "displayedproxymsg=1",
        "UseSSL=true",
        "",
        "[IBGateway]",
        "ApiOnly=true",
        "TrustedIPs=127.0.0.1",
        "LocalServerPort=$ApiPort",
        ""
    ) -join "`r`n"

    Write-Utf8NoBom -Path $Path -Content $content
}

if (-not $EnvFilePath) {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $EnvFilePath = Join-Path $repoRoot ".env"
}

$envMap = Read-EnvMap -Path $EnvFilePath

if (-not $envMap.ContainsKey("ALPHAEDGE_IB_USERNAME") -or -not $envMap["ALPHAEDGE_IB_USERNAME"]) {
    throw "ALPHAEDGE_IB_USERNAME is missing from $EnvFilePath"
}
if (-not $envMap.ContainsKey("ALPHAEDGE_IB_PASSWORD") -or -not $envMap["ALPHAEDGE_IB_PASSWORD"]) {
    throw "ALPHAEDGE_IB_PASSWORD is missing from $EnvFilePath"
}

$gatewayDirectory = Get-GatewayDirectory -EnvMap $envMap
$gatewayMajorVersion = Get-GatewayMajorVersion -GatewayDirectory $gatewayDirectory
$jtsRoot = Split-Path -Parent (Split-Path -Parent $gatewayDirectory)

$paperMode = $true
if ($envMap.ContainsKey("ALPHAEDGE_PAPER") -and $envMap["ALPHAEDGE_PAPER"]) {
    $paperMode = @("1", "true", "yes", "on") -contains $envMap["ALPHAEDGE_PAPER"].Trim().ToLower()
}

$tradingMode = if ($paperMode) { "paper" } else { "live" }
$apiPort = if ($envMap.ContainsKey("ALPHAEDGE_IB_PORT") -and $envMap["ALPHAEDGE_IB_PORT"]) {
    $envMap["ALPHAEDGE_IB_PORT"]
}
else {
    if ($paperMode) { "4002" } else { "4001" }
}

$downloadUrl = "https://github.com/IbcAlpha/IBC/releases/download/$IbcVersion/IBCWin-$IbcVersion.zip"
$zipPath = Join-Path $env:TEMP "IBCWin-$IbcVersion.zip"
$extractPath = Join-Path $env:TEMP "IBCWin-$IbcVersion"

Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath

if (Test-Path $extractPath) {
    Remove-Item $extractPath -Recurse -Force
}
Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
Get-ChildItem -Path $extractPath -Force | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $InstallRoot -Recurse -Force
}

$settingsPath = Join-Path $ConfigRoot "settings"
$logPath = Join-Path $ConfigRoot "logs"
$jtsIniPath = Join-Path $settingsPath "jts.ini"
New-Item -ItemType Directory -Path $ConfigRoot -Force | Out-Null
New-Item -ItemType Directory -Path $settingsPath -Force | Out-Null
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
Write-BootstrapJtsIni -Path $jtsIniPath -ApiPort $apiPort

$templateConfigPath = Join-Path $InstallRoot "config.ini"
$configPath = Join-Path $ConfigRoot "config.ini"
$configContent = Get-Content $templateConfigPath -Raw
$configContent = Set-IniValue -Content $configContent -Key "IbLoginId" -Value $envMap["ALPHAEDGE_IB_USERNAME"]
$configContent = Set-IniValue -Content $configContent -Key "IbPassword" -Value $envMap["ALPHAEDGE_IB_PASSWORD"]
$configContent = Set-IniValue -Content $configContent -Key "TradingMode" -Value $tradingMode
$configContent = Set-IniValue -Content $configContent -Key "IbDir" -Value $settingsPath
$configContent = Set-IniValue -Content $configContent -Key "OverrideTwsApiPort" -Value $apiPort
$configContent = Set-IniValue -Content $configContent -Key "AcceptIncomingConnectionAction" -Value "accept"
$configContent = Set-IniValue -Content $configContent -Key "AcceptNonBrokerageAccountWarning" -Value "yes"
$configContent = Set-IniValue -Content $configContent -Key "StoreSettingsOnServer" -Value "yes"
$configContent = Set-IniValue -Content $configContent -Key "ExistingSessionDetectedAction" -Value "primary"
$configContent = Set-IniValue -Content $configContent -Key "ReloginAfterSecondFactorAuthenticationTimeout" -Value "no"
Write-Utf8NoBom -Path $configPath -Content $configContent

$templateLauncherPath = Join-Path $InstallRoot "StartGateway.bat"
$launcherPath = Join-Path $InstallRoot "StartGatewayAlphaEdge.bat"
$launcherContent = Get-Content $templateLauncherPath -Raw
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set TWS_MAJOR_VRSN=.*$",
    "set TWS_MAJOR_VRSN=$gatewayMajorVersion",
    1
)
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set CONFIG=.*$",
    "set CONFIG=$configPath",
    1
)
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set TRADING_MODE=.*$",
    "set TRADING_MODE=$tradingMode",
    1
)
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set IBC_PATH=.*$",
    "set IBC_PATH=$InstallRoot",
    1
)
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set TWS_PATH=.*$",
    "set TWS_PATH=$jtsRoot",
    1
)
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set TWS_SETTINGS_PATH=.*$",
    "set TWS_SETTINGS_PATH=$settingsPath",
    1
)
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set LOG_PATH=.*$",
    "set LOG_PATH=$logPath",
    1
)
$launcherContent = [regex]::Replace(
    $launcherContent,
    "(?m)^set HIDE=.*$",
    "set HIDE=YES",
    1
)
Write-Utf8NoBom -Path $launcherPath -Content $launcherContent -Ascii

$envLines = Get-Content $EnvFilePath
$envLines = Set-OrAppend-EnvValue -Lines $envLines -Key "ALPHAEDGE_IB_LOGIN_MODE" -Value "ibc"
$envLines = Set-OrAppend-EnvValue -Lines $envLines -Key "ALPHAEDGE_IB_LAUNCHER_PATH" -Value $launcherPath
$envLines = Set-OrAppend-EnvValue -Lines $envLines -Key "ALPHAEDGE_IB_GATEWAY_PATH" -Value $gatewayDirectory
Write-Utf8NoBom -Path $EnvFilePath -Content (($envLines -join "`r`n") + "`r`n")

[pscustomobject]@{
    IbcVersion = $IbcVersion
    InstallRoot = $InstallRoot
    GatewayDirectory = $gatewayDirectory
    ConfigPath = $configPath
    LauncherPath = $launcherPath
    TradingMode = $tradingMode
    ApiPort = $apiPort
} | Format-List
