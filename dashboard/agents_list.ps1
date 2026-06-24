$env:PYTHONIOENCODING = 'utf-8'
$out = & openclaw agents list --json 2>&1 | Out-String
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$out
