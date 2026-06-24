# Wrapper — запуск Claw Dash из папки dashboard
$ClawDash = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "clawdash\start_clawdash.ps1"
& $ClawDash @args
