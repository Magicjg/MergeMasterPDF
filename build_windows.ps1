$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = Join-Path $projectRoot ".venv\Scripts\python.exe"
$specFile = Join-Path $projectRoot "MergeMasterPDF.spec"
$installerScript = Join-Path $projectRoot "installer.iss"
$mainScript = Join-Path $projectRoot "MergeMasterPDF.py"
$iconFile = Join-Path $projectRoot "icono.ico"
$buildDir = Join-Path $projectRoot "build"
$distDir = Join-Path $projectRoot "dist"
$appDir = Join-Path $distDir "MergeMasterPDF"
$buildInstaller = $env:MMP_BUILD_INSTALLER -eq "1"
$isccPath = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

function Compress-WithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,
        [Parameter(Mandatory = $true)]
        [string]$DestinationPath
    )

    $lastError = $null
    for ($attempt = 1; $attempt -le 5; $attempt++) {
        try {
            if (Test-Path $DestinationPath) {
                Remove-Item -LiteralPath $DestinationPath -Force
            }
            Compress-Archive -LiteralPath $SourcePath -DestinationPath $DestinationPath -Force
            return
        } catch {
            $lastError = $_
            Start-Sleep -Milliseconds (500 * $attempt)
        }
    }

    throw $lastError
}

if (-not (Test-Path $pythonExe)) {
    throw "No se encontro la .venv del proyecto en $pythonExe"
}

if (-not (Test-Path $specFile)) {
    throw "No se encontro el archivo spec en $specFile"
}

if (-not (Test-Path $mainScript)) {
    throw "No se encontro el archivo principal en $mainScript"
}

if (-not (Test-Path $iconFile)) {
    throw "No se encontro el icono del proyecto en $iconFile"
}

if ($buildInstaller -and -not (Test-Path $installerScript)) {
    throw "No se encontro el script del instalador en $installerScript"
}

Push-Location $projectRoot
try {
    $sourceText = Get-Content -LiteralPath $mainScript -Raw
    $versionMatch = [regex]::Match($sourceText, 'APP_VERSION\s*=\s*"([^"]+)"')
    if (-not $versionMatch.Success) {
        throw "No se pudo leer APP_VERSION desde $mainScript"
    }

    $appVersion = $versionMatch.Groups[1].Value
    $archiveFile = Join-Path $distDir "MergeMasterPDF-v$appVersion-windows-x64.zip"
    $setupFile = Join-Path $distDir "MergeMasterPDF-Setup-v$appVersion.exe"

    foreach ($targetDir in @($buildDir, $distDir)) {
        if (Test-Path $targetDir) {
            Remove-Item -LiteralPath $targetDir -Recurse -Force
        }
    }

    & $pythonExe -m PyInstaller --noconfirm --clean $specFile
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    $bundledConfig = Join-Path $appDir "config.json"
    if (Test-Path $bundledConfig) {
        Remove-Item -LiteralPath $bundledConfig -Force
    }

    Compress-WithRetry -SourcePath $appDir -DestinationPath $archiveFile

    if ($buildInstaller -and $isccPath) {
        & $isccPath `
            "/DMyAppVersion=$appVersion" `
            "/DMySourceDir=$appDir" `
            "/DMyOutputDir=$distDir" `
            "/DMyOutputBaseFilename=MergeMasterPDF-Setup-v$appVersion" `
            $installerScript
        if ($LASTEXITCODE -ne 0) {
            exit $LASTEXITCODE
        }
    }

    Write-Host ""
    Write-Host "Build completado."
    Write-Host "Carpeta: $appDir"
    Write-Host "ZIP: $archiveFile"
    if ($buildInstaller -and $isccPath) {
        Write-Host "SETUP: $setupFile"
    } elseif ($buildInstaller) {
        Write-Host "SETUP: Inno Setup no encontrado, se omitio el instalador."
    } else {
        Write-Host "SETUP: omitido (define MMP_BUILD_INSTALLER=1 para generarlo)."
    }
} finally {
    Pop-Location
}
