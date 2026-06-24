Get-NetTCPConnection -LocalPort 18790 -ErrorAction SilentlyContinue | ForEach-Object -Process {
  $p = $_.OwningProcess
  if ($p -gt 0) {
    try { Stop-Process -Id $p -Force } catch { Write-Host "skip $p" }
  }
}
Start-Sleep 1
Write-Host "remaining:"
Get-NetTCPConnection -LocalPort 18790 -ErrorAction SilentlyContinue | Select-Object OwningProcess | Format-Table -HideTableHeaders
