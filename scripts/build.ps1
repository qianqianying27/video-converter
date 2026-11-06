# 打包脚本：PyInstaller onedir（内含 bin\ffmpeg.exe、bin\ffprobe.exe）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\build.ps1

param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "未找到 .venv，请先执行：python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

$ffmpeg = Join-Path $root "bin\ffmpeg.exe"
$ffprobe = Join-Path $root "bin\ffprobe.exe"
if (-not (Test-Path $ffmpeg) -or -not (Test-Path $ffprobe)) {
    throw "bin\ 中缺少 ffmpeg.exe / ffprobe.exe，请先运行 scripts\fetch_ffmpeg.ps1"
}

if (-not $SkipTests) {
    Write-Host "运行测试…"
    & $venvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "测试未通过，终止打包" }
}

Write-Host "PyInstaller 打包…"
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name VideoConverter `
    --add-data "bin;bin" `
    run.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

# 随包附带第三方许可说明（ffmpeg 为 GPL 构建，分发时需要）
$distDir = Join-Path $root "dist\VideoConverter"
Copy-Item (Join-Path $root "THIRD_PARTY_NOTICES.md") (Join-Path $distDir "THIRD_PARTY_NOTICES.md") -Force
Copy-Item (Join-Path $root "THIRD_PARTY_NOTICES.md") (Join-Path $distDir "_internal\bin\THIRD_PARTY_NOTICES.md") -Force

Write-Host "完成：$root\dist\VideoConverter"
