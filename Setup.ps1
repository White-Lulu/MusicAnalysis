$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$installTmp = Join-Path $PSScriptRoot 'install-tmp'
$null = New-Item -ItemType Directory -Path $installTmp -Force
$env:TEMP = $installTmp
$env:TMP = $installTmp
$env:PYTHONDONTWRITEBYTECODE = '1'
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
$runtime = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
& $runtime -m pip --disable-pip-version-check install --no-cache-dir --no-compile 'torch==2.8.0' 'torchaudio==2.8.0' --index-url https://download.pytorch.org/whl/cpu
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $runtime -m pip --disable-pip-version-check install --no-cache-dir --no-compile -r requirements.txt
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$siteRoot = (Resolve-Path -LiteralPath '.venv/Lib/site-packages').Path
# Pretrained inference uses the shipped DLLs. C++ build headers and link archives are development assets.
foreach ($relative in @('torch/include', 'tensorflow/include')) {
    $candidate = Join-Path $siteRoot $relative
    if (Test-Path -LiteralPath $candidate) {
        $target = (Resolve-Path -LiteralPath $candidate).Path
        if (-not $target.StartsWith($siteRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or (Get-Item -LiteralPath $target).LinkType) {
            throw 'Unexpected development-header path.'
        }
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
Get-ChildItem -LiteralPath (Join-Path $siteRoot 'torch/lib') -Filter '*.lib' -File | ForEach-Object {
    Remove-Item -LiteralPath $_.FullName -Force
}
& $runtime -m music_analysis.assets (Join-Path $PSScriptRoot 'models')
exit $LASTEXITCODE
