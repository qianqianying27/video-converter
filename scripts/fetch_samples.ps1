# 获取截图/演示用的示例素材（仅本地，不入库）
# - flower.mp4：MDN CC0 实拍素材（960x540，5s）
# - portrait.mp4：由 flower 裁剪出的竖屏版本（540x960）
# 用法：powershell -ExecutionPolicy Bypass -File scripts\fetch_samples.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$dir = Join-Path $root ".samples"
New-Item -ItemType Directory -Force $dir | Out-Null

$flower = Join-Path $dir "flower.mp4"
if (-not (Test-Path $flower)) {
    Write-Host "下载 flower.mp4（MDN CC0）…"
    curl.exe -L --fail --retry 3 -o $flower "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
    if ($LASTEXITCODE -ne 0) { throw "下载失败" }
}

$portrait = Join-Path $dir "portrait.mp4"
if (-not (Test-Path $portrait)) {
    Write-Host "生成 portrait.mp4…"
    $ffmpeg = Join-Path $root "bin\ffmpeg.exe"
    & $ffmpeg -hide_banner -y -i $flower -vf "crop=304:540:328:0,scale=540:960:flags=lanczos" `
        -c:v libx264 -preset veryfast -crf 20 -an $portrait
    if ($LASTEXITCODE -ne 0) { throw "生成竖屏素材失败" }
}

$bbb = Join-Path $dir "bbb.mp4"
if (-not (Test-Path $bbb)) {
    Write-Host "下载 bbb.mp4（Big Buck Bunny 720p 10s）…"
    curl.exe -L --fail --retry 3 -o $bbb "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_1MB.mp4"
    if ($LASTEXITCODE -ne 0) { throw "下载 bbb 失败" }
}

$bench = Join-Path $dir "bench_1080p.mp4"
if (-not (Test-Path $bench)) {
    Write-Host "生成 bench_1080p.mp4（30s 1080p，用于基准与演示）…"
    & $ffmpeg -hide_banner -y -stream_loop 2 -i $bbb -t 30 -vf scale=1920:1080 `
        -c:v libx264 -preset veryfast -crf 20 -c:a aac -b:a 128k $bench
    if ($LASTEXITCODE -ne 0) { throw "生成基准素材失败" }
}

Write-Host "素材就绪："
Get-ChildItem $dir -Filter *.mp4 | Select-Object Name, Length
