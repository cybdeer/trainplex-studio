# TrainPlex Reel 02 — whole edit pipeline, one re-runnable command (Windows PowerShell 5.1+).
#
#   powershell -ExecutionPolicy Bypass -File work\run_pipeline.ps1            # everything
#   powershell -ExecutionPolicy Bypass -File work\run_pipeline.ps1 -From qa   # resume at a stage
#
# Stages (in order): transcribe, normalise, align, face, data, audio, render, qa, report
# Inputs: clips\clip1.mp4, clip2.mp4, clip3.mp4 (720p takes today; drop in the 1080p Flow upscales with
# the same names and re-run — trims, captions, face boxes, graphics placement, audio and QA all re-derive).
# If whisper hears a new take differently, align_captions.py stops with a SPANS assert: re-map SPANS there.
param(
  [ValidateSet('transcribe', 'normalise', 'align', 'face', 'data', 'audio', 'render', 'qa', 'report')]
  [string]$From = 'transcribe'
)
# 'Continue': native tools (npx, ffmpeg, python) log to stderr; failures are caught by exit codes below.
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = '1'
$env:PATH = "C:\TrainPlex\tools\ffmpeg\bin;$env:PATH"
$py = 'C:\Users\DESKTOP\AppData\Local\Programs\Python\Python311\python.exe'
$stages = 'transcribe', 'normalise', 'align', 'face', 'data', 'audio', 'render', 'qa', 'report'
$start = [array]::IndexOf($stages, $From)

function Step([string]$name, [scriptblock]$body) {
  if ([array]::IndexOf($stages, $name) -lt $start) { return }
  Write-Host "`n=== $name ===" -ForegroundColor Cyan
  $t = Get-Date
  & $body
  if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) { throw "stage '$name' failed (exit $LASTEXITCODE)" }
  Write-Host ("=== {0} done in {1:n0} s" -f $name, ((Get-Date) - $t).TotalSeconds) -ForegroundColor Cyan
}
function Remotion([string[]]$a) {
  Push-Location (Join-Path $Root 'remotion')
  try { & npx.cmd @a; if ($LASTEXITCODE -ne 0) { throw "npx $($a -join ' ') failed" } } finally { Pop-Location }
}

foreach ($d in 'work\transcripts', 'work\norm', 'work\render', 'work\audio', 'output\qa', 'work\qa\parts', 'remotion\public\clips') {
  New-Item -ItemType Directory -Force $d | Out-Null
}
foreach ($c in 1, 2, 3) { if (-not (Test-Path "clips\clip$c.mp4")) { throw "missing clips\clip$c.mp4" } }

Step 'transcribe' { & $py work\transcribe.py }          # whisper word timings (timing only)
Step 'normalise'  { & $py work\normalise.py }           # measured trims -> 1080x1920@30 Lanczos, edit.json, flow_merge_trims.json
Step 'align'      { & $py work\align_captions.py }      # exact script + whisper timing -> captions.json
Step 'face'       { & $py work\face_track.py }          # Haar face box on every frame -> face_boxes.json
Step 'data' {
  Copy-Item work\captions.json, work\edit.json, work\face_boxes.json remotion\src\data\ -Force
  Copy-Item work\norm\clip1.mp4, work\norm\clip2.mp4, work\norm\clip3.mp4 remotion\public\clips\ -Force
  Remotion @('tsc', '--noEmit')
}
Step 'audio'      { & $py work\audio_mix.py }           # HPF, de-ess test, -16 LUFS/clip, -14 LUFS master, TP limiter
Step 'render'     { & $py work\render.py }              # Remotion (PNG frames, CRF 18, BT.709) + mux + cover + QA grabs
Step 'qa' {
  foreach ($d in 'work\qa\g', 'work\qa\iso') { if (Test-Path $d) { Remove-Item -Recurse -Force $d } }
  Remotion @('remotion', 'render', 'src/index.ts', 'Reel02Graphics', (Join-Path $Root 'work\qa\g'), '--sequence', '--image-format=png',
             '--image-sequence-pattern=f[frame].[ext]', '--concurrency=4')
  foreach ($id in 'Cap1', 'Cap2', 'Cap3', 'EndScreenFG') {
    Remotion @('remotion', 'render', '..\work\qa\remotion_qa\index.tsx', $id, (Join-Path $Root "work\qa\iso\$id"), '--sequence',
               '--image-format=png', '--image-sequence-pattern=f[frame].[ext]', '--concurrency=4')
  }
  & node work\qa\run_dump.mjs
  if ($LASTEXITCODE -ne 0) { throw 'cue dump failed' }
  & $py work\qa\qa_landmarks.py
  if ($LASTEXITCODE -ne 0) { throw 'landmarks failed' }
  & $py work\qa\qa_reel02.py                             # exit 1 if any of the 9 checks fails
}
Step 'report'     { & $py work\pipeline_report.py }     # work/pipeline_report.md
Write-Host "`nDone. Deliverables in output\ ; QA in work\qa\qa_results.json ; report in work\pipeline_report.md" -ForegroundColor Green
