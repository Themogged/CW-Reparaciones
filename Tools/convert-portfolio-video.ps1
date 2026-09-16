param(
    [Parameter(Mandatory = $true)]
    [string] $Source,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]{1,63}$')]
    [string] $OutputName,

    [ValidateRange(0, 3600)]
    [int] $PreviewStart = 6,

    [ValidateRange(5, 15)]
    [int] $PreviewSeconds = 12,

    [ValidateRange(0, 3600)]
    [int] $PosterAt = 10
)

$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $Source -ErrorAction Stop).Path
if ([IO.Path]::GetExtension($sourcePath).ToLowerInvariant() -ne '.mp4') {
    throw 'El origen debe ser un archivo MP4.'
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$outputDirectory = Join-Path $projectRoot 'media_work'
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$previewPath = Join-Path $outputDirectory "$OutputName-preview.mp4"
$fullPath = Join-Path $outputDirectory "$OutputName-full.mp4"
$posterPath = Join-Path $outputDirectory "$OutputName-poster.jpg"
foreach ($targetPath in @($previewPath, $fullPath, $posterPath)) {
    if (Test-Path -LiteralPath $targetPath) {
        throw "La salida ya existe: $targetPath. Use otro nombre; este script conserva las versiones previas."
    }
}

$ffmpegCommand = Get-Command 'ffmpeg' -ErrorAction SilentlyContinue
if ($ffmpegCommand) {
    $ffmpegPath = $ffmpegCommand.Source
} else {
    $pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $pythonPath)) {
        throw 'No se encontró ffmpeg ni el Python del entorno virtual.'
    }
    $ffmpegPath = & $pythonPath -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $ffmpegPath)) {
        throw 'Instale imageio-ffmpeg en .venv para convertir medios o instale ffmpeg en PATH.'
    }
}

& $ffmpegPath -hide_banner -loglevel error -n -ss $PosterAt -i $sourcePath `
    -frames:v 1 -vf 'scale=720:-2' -q:v 3 $posterPath
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el póster.' }

& $ffmpegPath -hide_banner -loglevel error -n -ss $PreviewStart -i $sourcePath `
    -t $PreviewSeconds -map '0:v:0' -an -vf 'scale=540:960:flags=lanczos' `
    -c:v libx264 -threads 2 -preset veryfast -crf 30 -maxrate 1200k `
    -bufsize 2400k -pix_fmt yuv420p -movflags '+faststart' -map_metadata -1 `
    $previewPath
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar el preview.' }

& $ffmpegPath -hide_banner -loglevel error -n -i $sourcePath -map '0:v:0' `
    -map '0:a:0?' -vf 'scale=720:1280:flags=lanczos' -c:v libx264 `
    -threads 2 -preset veryfast -crf 28 -maxrate 2200k -bufsize 4400k `
    -pix_fmt yuv420p -c:a aac -b:a 64k -ar 44100 `
    -movflags '+faststart' -map_metadata -1 $fullPath
if ($LASTEXITCODE -ne 0) { throw 'No se pudo generar la versión web completa.' }

Get-Item -LiteralPath $posterPath, $previewPath, $fullPath |
    Select-Object FullName, Length
