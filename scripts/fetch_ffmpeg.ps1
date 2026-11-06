# 下载 ffmpeg / ffprobe 到项目的 bin 目录（Windows）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1

param(
    [string]$Dest = (Join-Path $PSScriptRoot "..\bin")
)

$ErrorActionPreference = "Stop"

$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

New-Item -ItemType Directory -Force $Dest | Out-Null
$tmp = Join-Path $env:TEMP ("ffmpeg-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force $tmp | Out-Null
$zip = Join-Path $tmp "ffmpeg.zip"

try {
    Write-Host "下载 ffmpeg（约 170MB）：$url"
    curl.exe -L --fail --retry 3 -o $zip $url
    if ($LASTEXITCODE -ne 0) { throw "下载失败（curl 退出码 $LASTEXITCODE）" }

    Write-Host "解压…"
    tar -xf $zip -C $tmp
    if ($LASTEXITCODE -ne 0) { throw "解压失败（tar 退出码 $LASTEXITCODE）" }

    Get-ChildItem $tmp -Recurse -Include ffmpeg.exe, ffprobe.exe | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $Dest $_.Name) -Force
    }

    Write-Host "完成："
    Get-ChildItem $Dest | Select-Object Name, Length | Format-Table
}
finally {
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
