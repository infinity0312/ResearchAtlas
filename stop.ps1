$ErrorActionPreference='Stop'
$atlasState=Join-Path $PSScriptRoot 'data\processes.json'
if(Test-Path -LiteralPath $atlasState){
 $state=Get-Content -LiteralPath $atlasState -Raw | ConvertFrom-Json
 foreach($p in $state.PSObject.Properties){
  $proc=Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Value)" -ErrorAction SilentlyContinue
  if($proc -and $proc.ExecutablePath -eq (Join-Path $PSScriptRoot '.venv\Scripts\python.exe')){ & taskkill.exe /PID $p.Value /T /F }
 }
}
Write-Host 'Research Atlas stopped. Your data is retained.'
