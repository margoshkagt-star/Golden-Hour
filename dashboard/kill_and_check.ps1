$ports = Get-NetTCPConnection -LocalPort 18790 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique
foreach ($p in $ports) {
  if ($p -gt 0) {
    try {
      Stop-Process -Id $p -Force -ErrorAction Stop
      Write-Host "killed $p"
    } catch {
      Write-Host ("skip " + $p)
    }
  }
}
Start-Sleep 2
$ports2 = Get-NetTCPConnection -LocalPort 18790 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Sort-Object -Unique
foreach ($p in $ports2) {
  if ($p -gt 0) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction SilentlyContinue
    if ($proc) {
      $cl = $proc.CommandLine
      if ($cl.Length -gt 200) { $cl = $cl.Substring(0, 200) }
      Write-Host ("still listening " + $p + " : " + $proc.Name + " | parent=" + $proc.ParentProcessId + " | " + $cl)
    }
  }
}
