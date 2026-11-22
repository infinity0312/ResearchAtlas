param([switch]$NoBrowser)
$ErrorActionPreference='Stop'
$atlasRoot=$PSScriptRoot
$atlasPython=Join-Path $atlasRoot '.venv\Scripts\python.exe'
$atlasData=Join-Path $atlasRoot 'data'
if (-not (Test-Path -LiteralPath $atlasPython)) { throw 'Python environment missing. See README.md for setup.' }
if (-not (Test-Path -LiteralPath (Join-Path $atlasRoot 'dist\index.html'))) { throw 'Frontend build missing. Run npm run build.' }
New-Item -ItemType Directory -Path $atlasData -Force | Out-Null
Push-Location $atlasRoot
try { & $atlasPython -c 'from backend.db import init_db; init_db()'; if($LASTEXITCODE -ne 0){throw 'Database initialization failed.'} } finally { Pop-Location }
$atlasRunning=$false
try { $h=Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; $atlasRunning=$h.app -eq 'Research Atlas' } catch {}
$atlasPids=@{}
if (Test-Path -LiteralPath (Join-Path $atlasData 'processes.json')) { $old=Get-Content -LiteralPath (Join-Path $atlasData 'processes.json') -Raw | ConvertFrom-Json; foreach($p in $old.PSObject.Properties){$atlasPids[$p.Name]=$p.Value} }
if (-not $atlasRunning) {
 $p=Start-Process -FilePath $atlasPython -ArgumentList @('-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8765') -WorkingDirectory $atlasRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $atlasData 'server.log') -RedirectStandardError (Join-Path $atlasData 'server-error.log')
 $atlasPids.server=$p.Id
}
if (-not $atlasRunning -or -not $h.worker) {
 $p=Start-Process -FilePath $atlasPython -ArgumentList @('-m','backend.worker') -WorkingDirectory $atlasRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $atlasData 'worker.log') -RedirectStandardError (Join-Path $atlasData 'worker-error.log')
 $atlasPids.worker=$p.Id
}
$atlasPids | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $atlasData 'processes.json')
$ready=$false
for($i=0;$i -lt 15;$i++) { try { $r=Invoke-RestMethod 'http://127.0.0.1:8765/api/health' -TimeoutSec 2; if($r.app -eq 'Research Atlas'){$ready=$true;break} }catch{}; Start-Sleep -Milliseconds 500 }
if(-not $ready){throw 'Startup failed. Check data/server-error.log.'}
Write-Host 'Research Atlas is ready: http://127.0.0.1:8765'
if(-not $NoBrowser){Start-Process 'http://127.0.0.1:8765'}
